from pyserini.search import LuceneSearcher
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from sentence_transformers import CrossEncoder
import json
import argparse
import sys
from tqdm import tqdm
import torch


def generate_response(top_docs, searcher, device, model: AutoModelForSeq2SeqLM, tokenizer: AutoTokenizer):
    passages = [json.loads(searcher.doc(hit.docid).raw())['contents'] for hit in top_docs]
    text = ' '.join(passages)
    inputs = tokenizer.encode("summarize: " + text, return_tensors="pt", max_length=512, truncation=True).to(device)
    with torch.no_grad():
        summary_ids = model.generate(
            inputs,
            max_length=250,
            min_length=50,
            length_penalty=2.0,
            num_beams=4,
            early_stopping=True
        )
    summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
    return summary


def get_ptkb_statements(query, num_ptkb, ptkb, reranker):
    # Find the similarity of PTKB statements with the given query
    similarity_scores = [reranker.predict([[query, ptkb_statement]])[0] for ptkb_statement in ptkb.values()]

    # Pair each statement with its similarity score
    statement_score_pairs = list(zip(list(ptkb.values()), similarity_scores))

    # Sort the pairs based on the similarity scores in descending order
    sorted_pairs = sorted(statement_score_pairs, key=lambda x: x[1], reverse=True)

    # Extract the sorted responses
    sorted_ptkb_statements = [pair[0] for pair in sorted_pairs]

    # Return required number of PTKB statements
    return ' '.join(sorted_ptkb_statements[:num_ptkb])


def rewrite_utterance(context, utterance, num_ptkb, ptkb, device, reranker, model, tokenizer):
    input_text = "{} ||| {}".format(context, utterance)
    input_ids = tokenizer.encode(input_text, return_tensors="pt").to(device)
    with torch.no_grad():
        output_ids = model.generate(
            input_ids,
            max_length=250,
            length_penalty=2.0,
            num_beams=4,
            early_stopping=True
        )

    rewritten_utterance = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    if num_ptkb > 0:
        ptkb_statements = get_ptkb_statements(
            query=context + ' ' + utterance,
            num_ptkb=num_ptkb,
            ptkb=ptkb,
            reranker=reranker
        )
        return rewritten_utterance + ' ' + ptkb_statements
    return rewritten_utterance


def prepare_output_for_json(turn_id, sorted_responses, sorted_hits, searcher, res):
    turn_data = {
        "turn_id": turn_id,
        "responses": []
    }

    for i in range(len(sorted_responses)):
        response_data = {
            "rank": i + 1,
            "text": sorted_responses[i],
            "passage_provenance": [
                {
                    "id": hit.docid,
                    "text": json.loads(searcher.doc(hit.docid).raw())['contents'],
                    "score": hit.score
                } for hit in sorted_hits[i]
            ]
        }
        turn_data["responses"].append(response_data)

    res["turns"].append(turn_data)


def official_search(
        query_id: str,
        query: str,
        k: int,
        searcher: LuceneSearcher,
        res,
        num_response: int,
        num_psg: int,
        device,
        reranker: CrossEncoder,
        summarizer: AutoModelForSeq2SeqLM,
        tokenizer: AutoTokenizer
):
    hits = searcher.search(q=query, k=k)
    if len(hits) != 0:
        top_docs_for_generating_response = [hits[i:i + num_psg] for i in range(0, len(hits), num_psg)]

        # Based on num_response asked, we generate responses
        responses = [generate_response(
            top_docs=top_docs_for_generating_response[i],
            model=summarizer,
            tokenizer=tokenizer,
            searcher=searcher,
            device=device
        ) for i in range(num_response)]

        # Now we rank these responses by their semantic similarity to the query
        similarity_scores = [reranker.predict([[query, response]])[0] for response in responses]

        # Pair each response with its subset of hits and its similarity score
        triplets = [
            (responses[i], top_docs_for_generating_response[i], similarity_scores[i])
            for i in range(num_response)
        ]

        # Sort the triplets based on the similarity scores in descending order
        sorted_triplets = sorted(triplets, key=lambda x: x[2], reverse=True)

        # Extract the sorted responses and their corresponding subset of hits
        sorted_responses = [triplet[0] for triplet in sorted_triplets]
        sorted_hits = [triplet[1] for triplet in sorted_triplets]

        # Prepare output data for run file
        prepare_output_for_json(
            turn_id=query_id,
            sorted_responses=sorted_responses,
            sorted_hits=sorted_hits,
            searcher=searcher,
            res=res
        )
    else:
        print('No hits for QueryID: {}'.format(query_id))
        print('Query: {}'.format(query))


def trec_search(query_id: str, query: str, k: int, searcher: LuceneSearcher, res, tag: str):
    hits = searcher.search(q=query, k=k)
    for i in range(len(hits)):
        res.append('{} Q0 {} {} {} {}'.format(query_id, hits[i].docid, i + 1, hits[i].score, tag))


def get_query(turn, run_type, num_ptkb, ptkb, device, reranker=None, rewriter=None, tokenizer=None,
              previous_utterance=None):
    if run_type == 'automatic':
        utterance = turn['utterance']
        return rewrite_utterance(
            context=previous_utterance,
            utterance=utterance,
            model=rewriter,
            tokenizer=tokenizer,
            num_ptkb=num_ptkb,
            ptkb=ptkb,
            reranker=reranker,
            device=device
        )
    else:
        ptkb_provenance = turn['ptkb_provenance']
        if len(ptkb_provenance) != 0:
            # We use the PTKB provenance where possible
            ptkb_statements = ' '.join([ptkb[str(i)] for i in ptkb_provenance])
            return turn['resolved_utterance'] + ' ' + ptkb_statements
        return turn['resolved_utterance']


def main():
    parser = argparse.ArgumentParser("Search using Pyserini.")
    parser.add_argument("--data", help='JSON file of data.', required=True)
    parser.add_argument("--index", help='Path to index.', required=True)
    parser.add_argument('--save', help='File to save.')
    parser.add_argument('--k', help='Number of documents to retrieve. Default: 100.', default=100, type=int)
    parser.add_argument('--ret-model', help='Retrieval model to use. Default: BM25.', default='bm25', type=str)
    parser.add_argument('--res-type', help='Type of result file (trec|official). Default: trec.', default='trec',
                        type=str)
    parser.add_argument('--num-response', help='Number of responses to generate. Default: 3.', default=3, type=int)
    parser.add_argument('--num-psg', help='Number of passages to use to generate a responses. Default: 3.', default=3,
                        type=int)
    parser.add_argument('--run-name', help='Name of run.,', required=True, type=str)
    parser.add_argument('--run-type', help='Type of run (manual|automatic). Default: Manual,', default='manual',
                        type=str)
    parser.add_argument('--num-ptkb', help='Top-K PTKB statements to use for query rewriting. Default: 0.',
                        default=0, type=int)
    parser.add_argument('--rm3', help='Whether or not to use RM3 query expansion. Default: False.', action='store_true')
    parser.add_argument('--cuda', help='CUDA device number. Default: 0.', type=int, default=0)
    parser.add_argument('--use-cuda', help='Whether or not to use CUDA. Default: False.', action='store_true')
    args = parser.parse_args(args=None if sys.argv[1:] else ['--help'])

    summarizer = None
    summarizer_tokenizer = None
    reranker = None
    rewriter = None
    rewriter_tokenizer = None
    cuda_device = 'cuda:' + str(args.cuda)

    device = torch.device(cuda_device if torch.cuda.is_available() and args.use_cuda else 'cpu')
    print('Using device: {}'.format(device))
    print('Run Type ==> {}'.format(args.run_type))
    print('Result Type ==> {}'.format(args.res_type))
    print('Top-K PTKB statements to use for query rewriting ==> {}'.format(args.num_ptkb))
    print('Number of responses to generate ==> {}'.format(args.num_response))
    print('Number of passages to use for response generation ==> {}'.format(args.num_psg))

    if args.res_type == 'official':
        summarizer = AutoModelForSeq2SeqLM.from_pretrained('mrm8488/t5-base-finetuned-summarize-news')
        summarizer_tokenizer = AutoTokenizer.from_pretrained('mrm8488/t5-base-finetuned-summarize-news')
        reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        summarizer.to(device)
        print('Summarizer ==> mrm8488/t5-base-finetuned-summarize-news')
        print('Reranker ==> cross-encoder/ms-marco-MiniLM-L-6-v2')

    if args.run_type == 'automatic':
        rewriter = AutoModelForSeq2SeqLM.from_pretrained('castorini/t5-base-canard')
        rewriter.to(device)
        rewriter_tokenizer = AutoTokenizer.from_pretrained('castorini/t5-base-canard')
        print('Rewriter ==> castorini/t5-base-canard')

    print('Loading data...')
    with open(args.data, 'r') as f:
        data = json.load(f)
    print('[Done].')

    searcher = LuceneSearcher(index_dir=args.index)
    if args.ret_model == 'bm25':
        searcher.set_bm25()
        print('Retrieval Model ==> BM25')
    else:
        searcher.set_qld()
        print('Retrieval Model ==> QLD')
    if args.rm3:
        searcher.set_rm3()
    print('Use RM3 ==> {}'.format(args.rm3))

    if args.res_type == 'official':
        res = {
            "run_name": args.run_name,
            "run_type": args.run_type,
            "turns": []
        }
    else:
        res = []

    print('Performing search...')
    previous_utterance = ""
    for idx, d in enumerate(data):
        print('========PROCESSING CONVERSATION-{} OF {}=============='.format(idx + 1, len(data)))
        number = d['number']
        turns = d['turns']
        ptkb = d['ptkb']
        for turn in tqdm(turns, total=len(turns)):
            turn_id = turn['turn_id']
            query_id = number + '_' + str(turn_id)
            query = get_query(
                turn=turn,
                run_type=args.run_type,
                num_ptkb=args.num_ptkb,
                rewriter=rewriter,
                tokenizer=rewriter_tokenizer,
                ptkb=ptkb,
                previous_utterance=previous_utterance,
                reranker=reranker,
                device=device
            )

            if args.res_type == 'official':
                official_search(
                    query_id=query_id,
                    query=query,
                    k=args.k,
                    searcher=searcher,
                    res=res,
                    num_response=args.num_response,
                    num_psg=args.num_psg,
                    reranker=reranker,
                    summarizer=summarizer,
                    tokenizer=summarizer_tokenizer,
                    device=device
                )
            else:  # trec
                trec_search(
                    query_id=query_id,
                    query=query,
                    k=args.k,
                    searcher=searcher,
                    res=res,
                    tag=args.run_name
                )

            if args.run_type == 'automatic':
                previous_utterance += " ||| " + turn['utterance'] + " ||| " + turn['response']
    print('[Done].')

    print('Writing to run file...')
    with open(args.save, 'w') as f:
        if isinstance(res, list):
            for line in res:
                f.write("%s\n" % line)
        elif isinstance(res, dict):
            json.dump(res, f, indent=4)


if __name__ == '__main__':
    main()
