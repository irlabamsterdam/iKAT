# ikat-scripts

Scripts for TREC iKAT 2023: https://www.trecikat.com/

## Running the scripts

The `ikat_tools.py` script has 3 modes:

### 1. Segmenting the original collection

This will generate passages from the original collection, storing them into `.jsonl` (and optionally `.trecweb`) files while also computing a set of passages hashes.

Usage:
```bash
# run the segmentation using 16 worker processes. /path/to/save/results will end up containing
# multiple files from each worker:
#   worker_XX.jsonl : passages in JSONL format (compatible with JSONCollection in pyserini/anserini)
#   worker_XX.trecweb : passages in trecweb format (if enabled, use "-t" parameter to do this)
#   worker_XX_hashes.tsv : passage hashes, row format is [ClueWeb22-ID, passage ID, passage hash (MD5)]
python ikat_tools.py segment -i /path/to/collection -o /path/to/save/results -w 16
```

## 2. Generating a passage index

```bash
# this expects to find a set of .jsonl files (as produced in mode 1) in /path/to/inputs, and
# will create a pyserini index in /path/to/output. The "-t" parameter is used to set the
# number of threads that pyserini will use. 
python ikat_tools.py create_index -i /path/to/inputs -o /path/to/output -t 16
```

## 3. Verifying passage hashes

```bash
# /path/to/hashes should point to a directory containing .tsv file(s) in the same format as mode 1 produces
# /path/to/passages should point to a directory containing .jsonl file(s) in the same format as mode 1 produces
# (these 2 paths can be the same directory)
# /path/to/log/file should be a filename where any hash mismatches will be logged If no mismatches
# are found the file will be empty. 
python ikat_tools.py verify_hashes -H /path/to/hashes -c /path/to/passages -e /path/to/log/file
```

## Docker

To make it simpler to run the script in a consistent environment, you can use the provided Dockerfile:

```bash
docker build . -t ikat_tools

# 1. segmenting the collection using 16 worker processes
docker run -it --rm \
      -v /path/to/input:/input:ro \
      -v /path/to/output:/output:rw \
      ikat_tools segment -i /input -o /output -w 16

# 2. generating an index with 16 threads
docker run -it --rm \
      -v /path/to/input:/input:ro \
      -v /path/to/output:/output:rw \
      ikat_tools create_index -i /input -o /output -t 16

# 3. verifying hashes
docker run -it --rm \
      -v /path/to/hashes:/hashes:ro \
      -v /path/to/passage_files:/passages:ro \
      -v /path/to/output:/output:rw \
      ikat_tools verify_hashes -H /hashes -c /passages -e /output/log.txt
```
