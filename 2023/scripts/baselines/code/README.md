# Baseline Runs

This script can be used to create baseline runs. It uses Pyserini and integrates it with state-of-the-art models from Huggingface's `transformers` library and the `sentence-transformers` library.

## Key Modules:
- `generate_response()`: Generates a summarized response given top retrieved documents.
- `get_ptkb_statements()`: Retrieves top-K statements from the PTKB that are similar to the query.
- `rewrite_utterance()`: Rewrites a query by incorporating relevant context and PTKB statements.
- `prepare_output_for_json()`: Prepares the response data in the official JSON format.
- `official_search()`: Performs the search and generates responses in the official format.
- `trec_search()`: Conducts the search and produces results in TREC format.
- `get_query()`: Determines the effective query based on the run type (manual or automatic) and any available PTKB provenance.

## Dependencies
- Pyserini
- Transformers
- Sentence-Transformers
- JSON
- argparse
- tqdm
- torch

## Usage

To run the script:

```
python <script_name>.py --data <data_file.json> --index <path_to_index> --save <output_file_name> --run-name <name_of_run>
```

### Arguments:

- `--data`: Path to the input JSON data file. *(required)*
- `--index`: Path to the Lucene index directory. *(required)*
- `--save`: File path to save the output results.
- `--k`: Number of documents to retrieve. Default is 100.
- `--ret-model`: Retrieval model to use. Options: `'bm25'`, `'qld'`. Default is `'bm25'`.
- `--res-type`: Type of result file. Options: `'trec'`, `'official'`. Default is `'trec'`.
- `--num-response`: Number of responses to generate. Default is 3.
- `--num-psg`: Number of passages to use for generating a response. Default is 3.
- `--run-name`: Name of the run. *(required)*
- `--run-type`: Type of run. Options: `'manual'`, `'automatic'`. Default is `'manual'`.
- `--num-ptkb`: Top-K PTKB statements to use for query rewriting. Default is 0.
- `--rm3`: Flag to indicate whether or not to use RM3 query expansion. Default is False.
- `--cuda`: CUDA device number. Default is 0.
- `--use-cuda`: Flag to indicate whether or not to use CUDA. Default is False.

## Note:
- When using `--res-type` as `'official'`, the script will load the summarizer `'mrm8488/t5-base-finetuned-summarize-news'` and the reranker `'cross-encoder/ms-marco-MiniLM-L-6-v2'`.
- When using `--run-type` as `'automatic'`, the script will load the rewriter `'castorini/t5-base-canard'`.

## License

MIT License. See the LICENSE file for details.
