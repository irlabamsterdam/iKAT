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
# Abort the run if more than 50 warnings of any type are generated
python3 main.py <run file path> -m 50
# Set a 10s timeout for gRPC calls to the validation service
python3 main.py <run file path> -t 10
```

The script logs to stdout and to a file in the current working directory named `<run_file>.errlog` (e.g. a run file named `sample_run.json` will have logs saved to `sample_run.json.errlog`).

## What does the script check?

This is a summary of the checks that the script performs on a run file.

 * Can the file be parsed as valid JSON?
 * Can the JSON be parsed into the protocol buffer format defined in `protocol_buffers/run.proto`?
 * Does the run file have at least one turn? 
 * Is the `run_name` field non-empty?
 * Is the `run_type` field non-empty and set to `automatic` or `manual`?
 * Does the number of turns match that of the selected topic?
 * For each turn in the run:
   * Is the turn ID valid and matches an entry in the topics file?
   * Is any turn ID higher than expected for the selected topic (e.g. turns 1-5 in the topic, but a turn has ID 6 in the run file)?
   * (optional, enabled by default) Do all the `passage_provenance` passage IDs appear in the collection?
   * For each response in the turn:
     * Does it have a rank > 0?
     * Do the ranks increase with successive responses?
     * Does the response have a non-empty `text` field?
     * For each `passage_provenance` entry:
       * Does it have a score less than the previous entry?
       * Does it have a passage ID containing a single colon and beginning with 'clueweb22-'?
     * Are there less than 1000 `passage_provenance` entries listed for the response?
     * Is there at least one `passage_provenance` with its `used` field set to True in the response?
     * Does the response have at least one `passage_provenance` entry?
     * Does the response have at least one `ptkb_provenance` entry?
     * For each `ptkb_provenance` entry:
       * Does it have a non-empty ID?
       * Does the ID appear in the `ptkb` field of the topic data?
       * Does the text given match that in the topic data?
       * Does it have a score less than the previous entry?


## Tests

There are some tests provided along with the validation script in the `tests` directory. To run them, use `pytest` from the `run_validation` directory, or `pytest --runslow` to run all tests including those that won't complete immediately. 
