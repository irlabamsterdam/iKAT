import os
import sys
import csv
import logging
import pathlib
from types import SimpleNamespace
from concurrent import futures

import pytest
import grpc

test_root = os.path.dirname(__file__)
sys.path.append(os.path.join(test_root, 'compiled_protobufs'))

from passage_validator import PassageValidator as PassageValidatorServicer
from passage_validator_pb2_grpc import add_PassageValidatorServicer_to_server
from passage_id_db import PassageIDDatabase, IKAT_PASSAGE_COUNT
from main import load_run_file, get_stub, GRPC_DEFAULT_TIMEOUT

# this file just contains the first 10k lines of the full hash file
SAMPLE_HASHES_PATH           = os.path.join(test_root, 'tests', 'data', 'sample_hashes.tsv')
# database version of the same file
SAMPLE_DB_PATH               = os.path.join(test_root, 'tests', 'data', 'sample_hashes.sqlite3')
SAMPLE_DB_COUNT              = 10000

FULL_DB_PATH                 = os.path.join(test_root, 'files', 'ikat_2023_passages_hashes.sqlite3')

TOPIC_DATA_PATH              = os.path.join(test_root, '..', '..', 'data')
TOPIC_DATA_FILE              = os.path.join(TOPIC_DATA_PATH, '2024_test_topics.json')
# TODO replace with a real baseline run file
BASELINE_RUN_FILE_PATH       = os.path.join(test_root, '..', 'baselines', 'runs')
BASELINE_RUN_FILE            = os.path.join(test_root, 'tests', 'data', 'sample_run.json')

RUN_FILE_PATH_NO_PTKB        = os.path.join(test_root, 'tests', 'data', 'sample_run_no_ptkb.json')
RUN_FILE_PATH_INVALID_SCORES = os.path.join(test_root, 'tests', 'data', 'sample_run_invalid_scores.json')
RUN_FILE_PATH_INVALID_PTKB   = os.path.join(test_root, 'tests', 'data', 'sample_run_missing_ptkb_fields.json')
RUN_FILE_PATH_RENAMED_FIELDS = os.path.join(test_root, 'tests', 'data', 'sample_run_renamed_fields.json')

@pytest.fixture
def sample_database(tmp_path: pathlib.PurePath):
    # create a temporary SQLite database from the contents of sample_hashes.tsv
    hdb = PassageIDDatabase(str(tmp_path / 'temp.sqlite3'))
    hdb.open()
    hdb.populate(SAMPLE_HASHES_PATH, 5000, 10000)
    yield hdb
    hdb.close()

@pytest.fixture
def sample_ids():
    # return a list of the valid IDs from sample_hashes.tsv
    ids = []
    with open(SAMPLE_HASHES_PATH, 'r') as f:
        rdr = csv.reader(f, delimiter='\t')
        ids = [f'{line[0]}:{line[1]}' for line in rdr]
    yield ids

@pytest.fixture
def topic_data_file():
    yield TOPIC_DATA_FILE

@pytest.fixture
def baseline_run_file():
    yield BASELINE_RUN_FILE

@pytest.fixture
def run_file_path_no_ptkb():
    yield RUN_FILE_PATH_NO_PTKB

@pytest.fixture
def run_file_path_invalid_scores():
    yield RUN_FILE_PATH_INVALID_SCORES

@pytest.fixture
def run_file_path_missing_ptkb_fields():
    yield RUN_FILE_PATH_INVALID_PTKB

@pytest.fixture
def run_file_path_renamed_fields():
    yield RUN_FILE_PATH_RENAMED_FIELDS

@pytest.fixture
def default_validate_args():
    yield SimpleNamespace(
        path_to_run_file=BASELINE_RUN_FILE,
        max_warnings=750,
        skip_passage_validation=False,
        fileroot=TOPIC_DATA_PATH,
        timeout=GRPC_DEFAULT_TIMEOUT,
    )

@pytest.fixture
def sample_turn(baseline_run_file: str):
    run = load_run_file(baseline_run_file)
    turn = run.turns[0]
    yield turn

@pytest.fixture
def test_logger(scope='module'):
    logger = logging.Logger('test_logger')
    yield logger

@pytest.fixture(scope='module')
def servicer_params_full():
    yield (FULL_DB_PATH, IKAT_PASSAGE_COUNT)

@pytest.fixture
def servicer_params_test():
    yield (SAMPLE_DB_PATH, SAMPLE_DB_COUNT)

@pytest.fixture
def grpc_stub_test(grpc_server_test):
    yield get_stub(port=8099)

@pytest.fixture
def grpc_stub_test_invalid(grpc_server_test_invalid):
    yield get_stub()

@pytest.fixture(scope='module')
def grpc_stub_full(grpc_server_full):
    yield get_stub()

@pytest.fixture
def grpc_server_test(servicer_params_test):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_PassageValidatorServicer_to_server(PassageValidatorServicer(*servicer_params_test), server)

    server.add_insecure_port("[::]:8099")
    server.start()
    yield server

    server.stop(None)

@pytest.fixture
def grpc_server_test_invalid(servicer_params_test):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_PassageValidatorServicer_to_server(PassageValidatorServicer(*servicer_params_test), server)

    server.add_insecure_port("[::]:8999")
    server.start()
    yield server

    server.stop(None)

@pytest.fixture
def grpc_server_full_alt(servicer_params_full):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_PassageValidatorServicer_to_server(PassageValidatorServicer(*servicer_params_full), server)

    server.add_insecure_port("[::]:8199")
    server.start()
    yield server

    server.stop(None)

@pytest.fixture(scope='module')
def grpc_server_full(servicer_params_full):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_PassageValidatorServicer_to_server(PassageValidatorServicer(*servicer_params_full), server)

    server.add_insecure_port("[::]:8000")
    server.start()
    yield server

    server.stop(None)
