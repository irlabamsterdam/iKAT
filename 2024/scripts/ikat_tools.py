import argparse
import bz2
import csv
import hashlib
import json
import os
import queue
import subprocess
from multiprocessing import Manager, Process, Queue
from typing import IO, List, Tuple

import _csv
import tqdm

from spacy_passage_chunker import SpacyPassageChunker

# max number of records to have queued while segmenting
QUEUE_LIMIT = 10_000
# total number of records in the collection
RECORDS = 13_467_076
# total number of passages that should result after segmenting with this script
PASSAGES = 116_838_987

def open_file(filename: str) -> IO:
    """
    Open a file with/without bzip2 depending on file extension.
    """
    if filename.endswith('.bz2'):
        return bz2.open(filename, 'rt', encoding='utf-8')

    return open(filename, 'r', encoding='utf-8')

def write_passages_json(json_file: IO, passages: List[str], title: str, id: str, url: str) -> None:
    """
    Write a set of passages to a JSONL file (one per line).

    The record format is compatible with pyserini/anserini JSONCollection.
    """
    for i, passage in enumerate(passages):
        obj = {
            'id': f'{id}:{i}',
            'contents': passage,
            'url': url,
        }
        json_file.write(json.dumps(obj) + '\n')

def create_trecweb_entry(idx: str, url: str, title: str, body: str) -> str:
    """
    Create and return a trecweb entry as a single string.
    """
    return ''.join([
        '<DOC>\n',
        f'<DOCNO>{idx}</DOCNO>\n',
        '<DOCHDR>\n</DOCHDR>\n',
        '<HTML>\n',
        f'<TITLE>{title}</TITLE>\n',
        f'<URL>{url}</URL>\n',
        '<BODY>\n',
        body,
        '</BODY>\n',
        '</HTML>\n',
        '</DOC>'
    ])

def add_passage_ids(passages: List[str]) -> str:
    """
    Add trecweb tags to a list of passages.

    This just surrounds each passage with <PASSAGE></PASSAGE> tags
    and adds an "id" attribute taken from the index of the passage
    in the supplied list. 

    Returns the full set of tagged passages as a single string.
    """
    passage_splits = []

    for idx, passage in enumerate(passages):
        passage_splits.append('<PASSAGE id={}>'.format(idx))
        passage_splits.append(passage)
        passage_splits.append('</PASSAGE>')

    return '\n'.join(passage_splits)

def write_passages_trecweb(trecweb_file: IO, passages: List[str], title: str, id: str, url: str) -> None:
    """
    Write a set of a passages to a trecweb file.
    """
    passage_splits = add_passage_ids(passages)
    trecweb_entry = create_trecweb_entry(
        idx=id,
        url=url,
        title=title,
        body=passage_splits
    )
    trecweb_file.write(trecweb_entry + '\n')

def write_hashes(hash_file: '_csv._writer', cwid: str, passages: List[str]) -> None:
    """
    Write a set of passage hashes to a .tsv file.

    Each line has format:
        ClueWeb22-ID<tab>passage ID<tab>passage MD5
    """
    for i, p in enumerate(passages):
        md5 = hashlib.md5()
        md5.update(p.encode('utf-8'))
        hash_file.writerow([cwid, i, md5.hexdigest()])

def ikat_segmenter_worker(worker_id: int, line_queue: Queue, gen_trecweb: bool, output_path: str, max_len: int, stride: int) -> None:
    """
    Method executed by worker processes during segmentation.

    It sets up output files for the given <worker_id>, then reads records from
    the queue until none remain. Each record is segmented into passages using
    spaCy, then written to JSONL and possibly trecweb files if selected. 

    Additionally a file containing MD5 hashes of each passage is created. 
    """
    chunker = SpacyPassageChunker(max_len=max_len, stride=stride)
    count = 0

    output_json = open(os.path.join(output_path, f'worker_{worker_id:02d}.jsonl'), 'w', encoding='utf-8')
    output_trecweb = open(os.path.join(output_path, f'worker_{worker_id:02d}.trecweb'), 'w', encoding='utf-8') if gen_trecweb else None
    output_hashes = open(os.path.join(output_path, f'worker_{worker_id:02d}_hashes.tsv'), 'w')
    hash_writer = csv.writer(output_hashes, delimiter='\t')

    while True:
        try:
            # the main process reads lines from the input files and adds them
            # to this queue. if we fail to retrieve a new line from the queue
            # then it indicates the input files are exhausted and this process
            # can exit
            line = line_queue.get(timeout=2.0)
        except queue.Empty:
            print(f'Worker {worker_id} found empty queue, exiting')
            break

        d = json.loads(line.strip())
        # titles seem to be the first line of the Clean-Text field
        title = d['Clean-Text'].split('\n')[0]
        # URLs have a trailing newline to remove
        url = d['URL'].strip()
        id = d['ClueWeb22-ID']
        
        # run the text through spaCy after removing newline chars
        doc_text = d['Clean-Text'].replace('\r', ' ').replace('\n', ' ')
        chunker.tokenize_document(doc_text)
        passages = chunker.chunk_document()

        # write outputs in one or both formats, plus passage hashes
        write_passages_json(output_json, passages, title, id, url)
        
        if output_trecweb is not None:
            write_passages_trecweb(output_trecweb, passages, title, id, url)

        write_hashes(hash_writer, id, passages)

        count += 1
        if count % 10_000 == 0:
            # Spacy models have associated data which can seemingly grow indefinitely as
            # new data is fed through it. Reloading the model periodically is the recommended
            # way to avoid this causing OOM conditions:
            # https://github.com/explosion/spaCy/discussions/10015
            chunker = SpacyPassageChunker(max_len, stride)

    output_hashes.close()
    if output_json is not None:
        output_json.close()
    if output_trecweb is not None:
        output_trecweb.close()

def get_next_line(handles: List[IO]) -> Tuple[str, int]:
    """
    Read the first available line from a set of file handles.

    Returns a tuple of (line, index of source file handle)
    """
    for i, h in enumerate(handles):
        line = h.readline()
        if len(line) > 0:
            return line.strip(), i

    return "", -1

def ikat_segmenter(args):
    """
    Segment the iKAT collection into JSONL and optionally trecweb files.
    """
    if not os.path.exists(args.input):
        raise Exception(f'Input path {args.input} not found')

    # allow input files to be compressed or uncompressed...
    input_files_bz2 = [f for f in os.listdir(args.input) if f.endswith('.json.bz2')]
    input_files_jsonl = [f for f in os.listdir(args.input) if f.endswith('.json')]

    # ... but not both
    if len(input_files_bz2) > 0 and len(input_files_jsonl) > 0:
        raise Exception(f'Found a mix of {len(input_files_bz2)} .json.bz2 files and \
                                {len(input_files_jsonl)} .json files. Only 1 type of file must exist in the selected folder')

    if len(input_files_bz2) > 0:
        input_files = [os.path.join(args.input, f) for f in input_files_bz2]
    elif len(input_files_jsonl) > 0:
        input_files = [os.path.join(args.input, f) for f in input_files_jsonl]
    else:
        raise Exception(f'No input files found in {args.input}')

    print(f'Found {len(input_files)} data files in {args.input}')
    
    file_handles = [open_file(f) for f in input_files]
    # a multiprocess Queue object used to send data to the worker processes
    line_queue = Manager().Queue(QUEUE_LIMIT)

    # fill the queue up to the limit so the workers have initial
    # content to get started with 
    for i in range(QUEUE_LIMIT):
        line, _ = get_next_line(file_handles)
        if len(line) == 0:
            break

        line_queue.put(line)

    workers = []
    # create and start the worker processes
    for i in range(args.num_workers):
        p = Process(target=ikat_segmenter_worker, args=(i, line_queue, args.trecweb, args.output, args.max_len, args.stride))
        p.start()
        workers.append(p)

    with tqdm.tqdm(total=RECORDS) as pbar:
        pbar.update(line_queue.qsize())

        while True:
            line, from_handle = get_next_line(file_handles)
            if len(line) == 0:
                break

            # <from_handle> indicates the index in file_handles that
            # <line> came from. If this is > 0 it indicates the previous
            # handle(s) are exhausted and can be closed + removed from the
            # list for future iterations
            if from_handle > 0:
                for i in range(from_handle):
                    file_handles[i].close()
                file_handles = file_handles[from_handle:]

            line_queue.put(line)
            pbar.update(1)

    for w in workers:
        w.join()

    for h in file_handles:
        h.close()


def ikat_generate_index(args):
    """
    Generate an index from passages in JSONL files using pyserini.
    """
    if not os.path.exists(args.input):
        raise Exception(f'Input directory {args.input} does not exist')

    os.makedirs(args.output, exist_ok=True)

    collection_type = 'JsonCollection'
    print(f'Generating index from {args.input} using collection type {collection_type}, saving output to {args.output}')
    subprocess.run(['python3', '-m', 'pyserini.index.lucene',
                    '-collection', collection_type, 
                    '-generator', 'DefaultLuceneDocumentGenerator',
                    '-threads', str(args.threads),
                    '-input', args.input,
                    '-index', args.output,
                    '-storePositions', '-storeRaw', '-storeDocvectors'])

def ikat_verify_hashes(args):
    """
    Verify a set of precomputed passage hashes against a set of passages.
    """
    if not os.path.exists(args.hashes):
        raise Exception(f'Hashes directory {args.hashes} does not exist')
    
    if not os.path.exists(args.collection):
        raise Exception(f'Collection directory {args.collection} does not exist')

    existing_hashes = {}

    hash_files = [f for f in os.listdir(args.hashes) if f.endswith('.tsv')]
    collection_files = [f for f in os.listdir(args.collection) if f.endswith('.jsonl')]

    if len(hash_files) == 0:
        raise Exception(f'Failed to find any .tsv files in {args.hashes}')

    if len(collection_files) == 0:
        raise Exception(f'Failed to find any .jsonl files in {args.collection}')

    print(f'> Will verify hashes from {len(hash_files)} .tsv files in {len(collection_files)} .jsonl files')

    # read all the hashes from the .tsv file(s)
    with tqdm.tqdm(desc='Reading hashes', total=PASSAGES) as pbar:
        for i, hash_file in enumerate(hash_files):
            reader = csv.reader(open(os.path.join(args.hashes, hash_file), 'r'), delimiter='\t')
            for row in reader:
                clueweb_id, passage_id, passage_hash = row
                existing_hashes[f'{clueweb_id}:{passage_id}'] = passage_hash
                pbar.update(1)

    errors = 0
    # now scan through all the JSONL files, compute fresh hashes and compare to the existing ones
    print(f'> Verifying hashes in {len(args.collection)} files')
    with tqdm.tqdm(desc='Verifying hashes', total=PASSAGES) as pbar, open(args.errors, 'w') as error_file:
        for collection_file in collection_files:
            with open(os.path.join(args.collection, collection_file), 'r', encoding='utf-8') as f:
                while True:
                    line = f.readline()
                    if len(line) == 0:
                        break

                    data = json.loads(line.strip())

                    passage_id = data['id']
                    assert(passage_id in existing_hashes)
                    passage_content = data['contents']
                    pmd5 = hashlib.md5()
                    pmd5.update(passage_content.encode('utf-8'))
                    computed_hash = pmd5.hexdigest()
                    existing_hash = existing_hashes[passage_id]

                    if computed_hash != existing_hash:
                        print(f'> ERROR: hash mismatch in {collection_file} on passage {passage_id}, computed hash {computed_hash}, existing hash {existing_hash}')
                        errors += 1
                        error_file.write(f'{collection_file},{passage_id},{computed_hash},{existing_hash}\n')

                    pbar.update(1)

    print(f'Hash verification finished with {errors} errors')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True, help='sub-command help')

    segment_parser = subparsers.add_parser('segment', help='Segment the collection into JSONL and/or trecweb files')
    segment_parser.add_argument('-i', '--input', help='Path to directory containing iKAT JSONL files (either .json.bz2 or .jsonl)', required=True, type=str)
    segment_parser.add_argument('-t', '--trecweb', help='Generate trecweb files containing passages', action='store_true')
    segment_parser.add_argument('-o', '--output', help='Path to save output files', required=True, type=str)
    segment_parser.add_argument('-w', '--num_workers', help='Number of parallel workers to use', default=8, type=int)
    segment_parser.add_argument('-m', '--max_len', help='Max length parameter for SpacyPassageChunker', default=10, type=int)
    segment_parser.add_argument('-s', '--stride', help='Stride parameter for SpacyPassageChunker', default=5, type=int)
    segment_parser.set_defaults(func=ikat_segmenter)

    create_index_parser = subparsers.add_parser('create_index', help='Generate pyserini index from JSONL passage data')
    create_index_parser.add_argument('-i', '--input', help='Path to directory containing passage JSONL files', required=True, type=str)
    create_index_parser.add_argument('-o', '--output', help='Path to save output files', required=True, type=str)
    create_index_parser.add_argument('-t', '--threads', help='Number of Pyserini threads to use', default=8, type=int)
    create_index_parser.set_defaults(func=ikat_generate_index)

    verify_parser = subparsers.add_parser('verify_hashes', help='Verify a set of hashes against a segmented collection')
    verify_parser.add_argument('-H', '--hashes', help='Path to directory containing passage hashes in .tsv file(s)', required=True, type=str)
    verify_parser.add_argument('-c', '--collection', help='Path to directory containing segmented collection in .jsonl file(s)', required=True, type=str)
    verify_parser.add_argument('-e', '--errors', help='Filename to save errors found during verification', required=True, type=str)
    verify_parser.set_defaults(func=ikat_verify_hashes)

    args = parser.parse_args()
    args.func(args)
