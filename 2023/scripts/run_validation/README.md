# iKAT run validator

## Initial configuration 

1. Copy the `ikat_2023_passage_hashes.tsv` file into `files`. 
2. Create a virtualenv, activate it, and run `pip install -r requirements.txt`.
3. Run `bash setup.sh`

This will compile the protocol buffers used by the gRPC validator service, and then build an SQLite database containing passage IDs to allow them to be looked up more efficiently. This might take 4-5 minutes depending on your hardware. 

## Running the validation script

First, start the passage validator service and leave it to run in the background: `python3 passage_validator_servicer.py files/ikat_2023_passages_hashes.sqlite3`

Run the main validation script (in another terminal but within the same virtual env). The script has several parameters you can view by running `python3 main.py -h`.

Some examples:

```shell
# Run with default parameters
python3 main.py <run file path>
# Run without having the validator service available
python3 main.py <run file path> -S
# Abort the run if more than 50 validation warnings are generated
python3 main.py <run file path> -m 50
# Abort the run if any gRPC errors occur contacting the validation service
python3 main.py <run file path> -s
# Set a 10s timeout for gRPC calls to the validation service
python3 main.py <run file path> -t 10
```

The script logs to stdout and to a file in the current working directory named `<run_file>.errlog` (e.g. a run file named `sample_run.json` will have logs saved to `sample_run.json.errlog`).

## Tests

There are some tests provided along with the validation script in the `tests` directory. To run them, use `pytest` from the `run_validation` directory, or `pytest --runslow` to run all tests including those that won't complete immediately. 
