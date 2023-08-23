import os
import sys
import copy
import pathlib

import pytest

from main import get_stub, load_topic_data, load_run_file
from main import validate_turn, validate_run, validate, GRPC_DEFAULT_TIMEOUT, EXPECTED_TOPIC_ENTRIES

def test_get_stub(grpc_server_test):
    assert(get_stub() is not None)

def test_load_topic_data(topic_data_file: str):
    topic_data = load_topic_data(topic_data_file)
    assert(len(topic_data) == EXPECTED_TOPIC_ENTRIES)

def test_load_invalid_topic_data(tmp_path: pathlib.PurePath):
    tmp_file = tmp_path / 'invalid.json'
    json_str = '{"foo": "bar"}'

    with open(tmp_file, 'w') as tf:
        tf.write(json_str)

    with pytest.raises(SystemExit) as pytest_exc:
        _ = load_topic_data(str(tmp_file))

    assert pytest_exc.type == SystemExit
    assert pytest_exc.value.code == 255

def test_load_missing_topic_data():
    with pytest.raises(Exception, match='Topics file foobar not found'):
        _ = load_topic_data('foobar')

def test_load_run_file(run_file_path: str):
    load_run_file(run_file_path)

def test_validate_invalid_run_file(tmp_path: pathlib.PurePath):
    tmp_file = tmp_path / 'invalid.json'
    json_str = '{"foo": "bar"}'
    
    with open(tmp_file, 'w') as tf:
        tf.write(json_str)

    with pytest.raises(SystemExit) as pytest_exc:
        _ = load_run_file(str(tmp_file))

    assert pytest_exc.type == SystemExit
    assert pytest_exc.value.code == 255

def test_validate_run_file_missing_run_name(tmp_path: pathlib.PurePath, run_file_path: str):
    tmp_file = tmp_path / 'missing_run_name.json'
    json_str = '{ "run_type": "manual", "turns": [] }'

    with open(tmp_file, 'w') as tf:
        tf.write(json_str)

    with pytest.raises(SystemExit) as pytest_exc:
        _ = load_run_file(str(tmp_file))

    assert pytest_exc.type == SystemExit
    assert pytest_exc.value.code == 255

def test_validate_run_file_missing_turns(tmp_path: pathlib.PurePath, run_file_path: str):
    tmp_file = tmp_path / 'missing_turns.json'
    json_str = '{ "run_type": "manual", "run_name": "missing_turns"}'

    with open(tmp_file, 'w') as tf:
        tf.write(json_str)

    with pytest.raises(SystemExit) as pytest_exc:
        _ = load_run_file(str(tmp_file))

    assert pytest_exc.type == SystemExit
    assert pytest_exc.value.code == 255

def test_validate_missing_run_file():
    with pytest.raises(OSError):
        _ = load_run_file('foobar')

def test_validate_turn(topic_data_file, run_file_path: str, grpc_stub_test, sample_turn):
    topic_data = load_topic_data(topic_data_file)
    topic_id = sample_turn.turn_id.split('_')[0]
    warnings, service_errors = validate_turn(sample_turn, topic_data[topic_id], grpc_stub_test, GRPC_DEFAULT_TIMEOUT)
    assert(warnings == 0)
    assert(service_errors == 0)

def test_validate_run(topic_data_file, run_file_path: str, grpc_stub_test, default_validate_args):
    args = default_validate_args
    topic_data = load_topic_data(topic_data_file)
    run = load_run_file(run_file_path)
    assert(len(run.turns) == 6)
    
    turns_validated, service_errors, total_warnings = validate_run(run, topic_data, grpc_stub_test, args.max_warnings, args.timeout)

    assert(turns_validated == 6)
    assert(service_errors == 0)
    assert(total_warnings == 0)

@pytest.mark.slow
def test_validate_run_invalid(topic_data_file, run_file_path: str, grpc_stub_test_invalid, default_validate_args):
    args = default_validate_args
    topic_data = load_topic_data(topic_data_file)
    run = load_run_file(run_file_path)
    assert(len(run.turns) == 6)

    # test that the script exits when it can't contact the grpc service
    with pytest.raises(SystemExit) as pytest_exc:
        _, _, _ = validate_run(run, topic_data, grpc_stub_test_invalid, args.max_warnings, args.timeout)

    assert pytest_exc.type == SystemExit
    assert pytest_exc.value.code == 255

def test_validate_run_no_service(topic_data_file, run_file_path: str, default_validate_args):
    args = default_validate_args
    topic_data = load_topic_data(topic_data_file)
    run = load_run_file(run_file_path)
    assert(len(run.turns) == 6)
    
    turns_validated, service_errors, total_warnings = validate_run(run, topic_data, None, args.max_warnings, args.timeout)
    assert(turns_validated == 6)
    assert(service_errors == 0)
    assert(total_warnings == 0)

@pytest.mark.slow
def test_validate(default_validate_args, grpc_server_full):
    args = default_validate_args

    turns_validated, service_errors, total_warnings = validate(args.path_to_run_file, args.fileroot, args.max_warnings, args.skip_passage_validation, args.timeout)
    assert(turns_validated == 6)
    assert(service_errors == 0)
    assert(total_warnings == 0) 

@pytest.mark.slow
def test_validate_no_service(default_validate_args, grpc_server_full):
    args = default_validate_args

    # terminate the service
    grpc_server_full.stop(None)

    turns_validated, service_errors, total_warnings = validate(args.path_to_run_file, args.fileroot, args.max_warnings, args.skip_passage_validation, args.timeout)
    assert(turns_validated == 6)
    assert(service_errors == 6)
    assert(total_warnings == 0) 

@pytest.mark.slow
def test_validate_no_service_skip_validation(default_validate_args, grpc_server_full):
    args = default_validate_args
    args.skip_passage_validation = True

    # terminate the service
    grpc_server_full.stop(None)

    turns_validated, service_errors, total_warnings = validate(args.path_to_run_file, args.fileroot, args.max_warnings, args.skip_passage_validation, args.timeout)
    assert(turns_validated == 6)
    assert(service_errors == 0)
    assert(total_warnings == 0) 

def test_validate_empty(default_validate_args):
    args = default_validate_args
    args.path_to_run_file = 'foobar'
    with pytest.raises(FileNotFoundError):
        _, _, _ = validate(args.path_to_run_file, args.fileroot, args.max_warnings, args.skip_passage_validation, args.timeout)

def test_validate_small(default_validate_args, grpc_server_test):
    args = default_validate_args
    
    # this should abort after generating enough warnings, since the smaller database won't match most of the IDs
    #with pytest.raises(SystemExit) as pytest_exc:
    turns_validated, service_errors, total_warnings = validate(args.path_to_run_file, args.fileroot, args.max_warnings, args.skip_passage_validation, args.timeout)
    assert(turns_validated == 6)
    assert(service_errors == 0)
    assert(total_warnings == 0)

def test_validate_passages_used(default_validate_args, grpc_stub_test, topic_data_file: str, run_file_path: str):
    # check that we get warnings if no passages in the provenance list are marked as "used"
    args = default_validate_args
    topic_data = load_topic_data(topic_data_file)
    run = load_run_file(run_file_path)
    assert(len(run.turns) == 6)

    # update the first 2 turns to have no "used" passages
    for i in range(2):
        for response in run.turns[i].responses:
            for pprov in response.passage_provenance:
                pprov.used = False
    
    turns_validated, service_errors, total_warnings = validate_run(run, topic_data, grpc_stub_test, args.max_warnings, args.timeout)

    assert(turns_validated == 6)
    assert(service_errors == 0)
    assert(total_warnings == 6) # 3 responses in each turn in the sample file

def test_validate_no_ptkb_results(default_validate_args, grpc_stub_test, topic_data_file: str, run_file_path_no_ptkb: str):
    args = default_validate_args
    topic_data = load_topic_data(topic_data_file)
    run = load_run_file(run_file_path_no_ptkb)

    turns_validated, _, total_warnings = validate_run(run, topic_data, grpc_stub_test, args.max_warnings, args.timeout)
    assert(turns_validated == len(run.turns))
    assert(total_warnings == len(run.turns)) # should be 1 warning per turn

def test_validate_non_numeric_scores(default_validate_args, run_file_path_invalid_scores: str):
    args = default_validate_args

    # test that a file with invalid scores doesn't parse
    with pytest.raises(SystemExit) as pytest_exc:
        _, _, _ = validate(run_file_path_invalid_scores, args.fileroot, args.max_warnings, args.skip_passage_validation, args.timeout)

    assert(pytest_exc.type == SystemExit)
    assert(pytest_exc.value.code == 255)

def test_validate_missing_ptkb_fields(default_validate_args, run_file_path_missing_ptkb_fields: str, topic_data_file: str):
    args = default_validate_args
    topic_data = load_topic_data(topic_data_file)
    run = load_run_file(run_file_path_missing_ptkb_fields)
    assert(len(run.turns) == 6)
    
    # this run has a ptkb_provenance field with the "id" and "text" entries deleted, it should cause the
    # script to exit when it encounters them
    with pytest.raises(SystemExit) as pytest_exc:
        _, _, _ = validate_run(run, topic_data, None, args.max_warnings, args.timeout)

    assert(pytest_exc.type == SystemExit)
    assert(pytest_exc.value.code == 255)

def test_validate_renamed_fields(run_file_path_renamed_fields: str):
    # this run has some field names changed to other values. this should be caught at the 
    # JSON => Protobuf parsing step
    with pytest.raises(SystemExit) as pytest_exc:
        run = load_run_file(run_file_path_renamed_fields)

    assert(pytest_exc.type == SystemExit)
    assert(pytest_exc.value.code == 255)
