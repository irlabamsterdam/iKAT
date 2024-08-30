import csv
import json
import argparse
import sys
import random

random.seed(12345)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--num_turns', help='Number of turns to generate (default is all)', default=-1, type=int)
    parser.add_argument('-p', '--num_passages', help='Number of passage provenances to add to each response', default=10, type=int)
    parser.add_argument('-r', '--num_responses', help='Number of responses to add to each turn', default=3, type=int)
    parser.add_argument('-k', '--num_ptkb', help='Number of PTKB provenance entries to add to each response', default=3, type=int)
    parser.add_argument('-T', '--run_type', help='Run type string', default='manual', type=str)
    parser.add_argument('-N', '--run_name', help='Run name string', default='generated_run', type=str)
    parser.add_argument('-o', '--output', help='Output file name', default='generated_run.json', type=str)
    parser.add_argument('-f', '--sample_ids', help='TSV file containing passage IDs', default='sample_hashes.tsv', type=str)
    parser.add_argument('-D', '--topic_data_file', help='2024 test topics JSON file path', default='../../../data/2024_test_topics.json')
    args = parser.parse_args()

    sample_ids = []
    with open(args.sample_ids, 'r') as f:
        rdr = csv.reader(f, delimiter='\t')
        for line in rdr:
            sample_ids.append(f'{line[0]}:{line[1]}')


    with open(args.topic_data_file, 'r') as f:
        all_topic_data = json.load(f)

    topic_data = None

    run = {}
    turns = []
    run['run_name'] = args.run_name
    run['run_type'] = args.run_type

    for topic in all_topic_data:
        num_turns = len(topic["turns"])
        for i in range(num_turns):
            turn = {}
            turn["turn_id"] = f"{topic['number']}_{i+1}"
            print(f'Generating turn {turn["turn_id"]}')

            responses = []
        
            print(f'Generating {args.num_responses} responses for turn')
            for nr in range(args.num_responses):
                response = {}
                response['rank'] = nr + 1
                response['text'] = 'some response text'

                passage_provs = []
                ptkb_provs = []

                print(f'Generating {args.num_passages} provenance entries and {args.num_ptkb} PTKB entries in response')
                for np in range(args.num_passages):
                    passage_prov = {}
                    passage_prov['id'] = sample_ids[random.randint(0, len(sample_ids)-1)]
                    passage_prov['text'] = 'some passage text'
                    passage_prov['score'] = 1.0 / (np + 1)
                    passage_prov['used'] = True
                    passage_provs.append(passage_prov)
                response['passage_provenance'] = passage_provs

                ptkbs = topic['ptkb']
                response["ptkb_provenance"] = random.sample(range(1, len(ptkbs)+1), args.num_ptkb)
                responses.append(response)

            turn['responses'] = responses
            turns.append(turn)

    run['turns'] = turns

    with open(args.output, 'w') as f:
        f.write(json.dumps(run))
