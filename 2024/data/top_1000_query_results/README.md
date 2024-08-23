This zip file contains queries extracted from the train and test topics in `queries_train.txt` and `queries_test.txt`, and the results of running them against the [iKAT searcher](https://ikat-searcher.grill.science) with a maximum of 1000 results and other parameters left at default values. 

The top-1000 results for each query are stored in the text files in `query_results_train` and `query_results_test`. The query-to-result-file mapping uses line numbers, counting from 0. So e.g. `query_results_train/query_results_000.txt` contains the results for the query on line 1 of `queries_train.txt`. 

Each line of each result file then has the format `ClueWeb22-ID,URL`.
