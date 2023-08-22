import argparse
import json
import logging
import os
import sys
from pathlib import PurePath
from typing import Tuple, Union, Any

import grpc
from google.protobuf.json_format import ParseDict

from utils import check_passage_provenance, check_ptkb_provenance, check_response, validate_passages

sys.path.append('./compiled_protobufs')
from passage_validator_pb2_grpc import PassageValidatorStub
from run_pb2 import Turn, iKATRun

GRPC_DEFAULT_TIMEOUT = 3.0
EXPECTED_TOPIC_ENTRIES = 25

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
streamHandler = logging.StreamHandler(sys.stdout)
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

def get_stub(ip: str = 'localhost', port: int = 8000) -> Union[None, PassageValidatorStub]:
    try:
        passage_validation_channel = grpc.insecure_channel(f'{ip}:{port}')
        passage_validation_client = PassageValidatorStub(passage_validation_channel)
    except grpc.RpcError as rpce:
        logger.error(f'A gRPC error occurred connecting to the validator service: {rpce.code().name}')
        return None

    return passage_validation_client

def load_topic_data(path: str) -> dict[str, dict[str, Any]]:
    if not os.path.exists(path):
        logger.error(f'Topics file {path} not found!')
        raise Exception(f'Topics file {path} not found!')

    try:
        topic_data = json.load(open(path, 'r'))
    except Exception as e:
        logger.error(f'Failed to load topics JSON data from {path}, exception: {e}')
        sys.exit(255)

    # check that topics were loaded correctly
    if len(topic_data) != EXPECTED_TOPIC_ENTRIES:
        logger.error(f'Topics file not loaded correctly (found {len(topic_data)} entries, expected 25)')
        sys.exit(255)

    # build a dict of the topics with "number" as the key
    topics_dict = {d['number']: d for d in topic_data}
    return topics_dict

def load_run_file(run_file_path: str) -> iKATRun:
    # validate structure
    with open(run_file_path, 'r', encoding='utf-8') as run_file:
        try:
            run = json.load(run_file)
            # check for expected attributes
            if 'run_name' not in run or 'run_type' not in run:
                raise Exception('Missing run_name/run_type entry')

            if 'turns' not in run:
                raise Exception('Missing turns entry')

            run = ParseDict(run, iKATRun())
        except Exception as e:
            logger.error(f'Run file not in the right format ({e})')
            sys.exit(255)

    return run

def validate_turn(turn: Turn, topic_data: dict[str, Any], stub: Union[None, PassageValidatorStub], timeout: float) -> Tuple[int, int]:
    """
    Validate a single turn from a run.

    Returns a 2-tuple of (number of warnings, number of service errors)
    """
    warning_count, service_errors = 0, 0

    logger.debug(f'Validating turn {turn.turn_id}')
    previous_rank = 0

    # will be None if skip_passage_validation was used
    if stub is not None:
        try:
            # if passage validation is enabled, this is where we make a gRPC call to the 
            # validation service to perform the passage ID checks
            warning_count += validate_passages(stub, logger, turn, timeout)
        except grpc.RpcError as rpce:
            logger.warning(f'A gRPC error occurred when validating passages (name={rpce.code().name}, message={rpce.details()})')
            service_errors += 1

    for response in turn.responses:
        # check the response:
        #   - does it have a rank > 0
        #   - does the rank increase with each response
        #   - does the response have text
        warning_count += check_response(response, logger, previous_rank, turn)
        previous_score = 1e9

        # check passage provenances
        #   - does the score decrease with each response
        for provenance in response.passage_provenance:
            warning_count += check_passage_provenance(previous_score, provenance, logger, turn.turn_id)
            previous_score = provenance.score

        if len(response.passage_provenance) == 0:
            logger.warning(f'Turn {turn.turn_id} has a response with no passage provenances')
            warning_count += 1
        elif len(response.passage_provenance) > 1000:
            logger.warning(f'Turn {turn.turn_id} has a response with >1000 passages ({len(response.passage_provenance)})')
            warning_count += 1

        if not hasattr(response, 'ptkb_provenance'):
            logger.warning(f'Missing "ptkb_provenance" field for a response in turn {turn.turn_id}')
            warning_count += 1
            break 

        if len(response.ptkb_provenance) == 0:
            logger.warning(f'No PTKB provenances listed for a response in turn {turn.turn_id}!')
            warning_count += 1
            break 

        prev_ptkb_score = 1e9
        ptkbs = topic_data['ptkb']

        for ptkb_prov in response.ptkb_provenance:
            warning_count += check_ptkb_provenance(ptkb_prov, turn, ptkbs, prev_ptkb_score, logger)
            prev_ptkb_score = ptkb_prov.score

    return warning_count, service_errors

def validate_run(run: iKATRun, topics_dict: dict[str, dict[str, Any]], stub: PassageValidatorStub, max_warnings: int, strict: bool, timeout: float) -> Tuple[int, int, int]:
    """
    Validates a run turn-by-turn, recording warnings and errors.
    """
    total_warnings, service_errors = 0, 0
    turns_validated = 0

    if len(run.run_name) == 0:
        logger.warning('Run has an empty run_name field')
        total_warnings += 1
    if len(run.run_type) == 0:
        logger.warning('Run has an empty run_type field')
        total_warnings += 1
    if run.run_type != 'automatic' and run.run_type != 'manual':
        logger.warning('Run has an unrecognised type, should be "automatic" or "manual"!')
        total_warnings += 1

    for turn in run.turns:
        # check if the turn ID is valid
        try:
            topic_id, turn_id = turn.turn_id.split('_')
        except Exception as e:
            logger.warning(f'Failed to parse turn ID "{turn.turn_id}", exception was {e}')
            total_warnings += 1
            continue

        if topic_id not in topics_dict:
            logger.warning(f'Turn {turn.turn_id} has an topic ID ({topic_id}) that is not in the topics JSON file!')
            total_warnings += 1
            continue # probably not worth doing anything else with this turn

        topic_data = topics_dict[topic_id]
        num_turns = len(topic_data['turns'])
        if int(turn_id) > num_turns:
            logger.warning(f'Turn {turn.turn_id} has a turn ID higher than the number of expected turns ({turn_id} > {num_turns})')
            total_warnings += 1

        if len(run.turns) != num_turns:
            logger.warning(f'The run contains {len(run.turns)} turns, but the topic contains {num_turns} turns')
            total_warnings += 1

        _warnings, _service_errors = validate_turn(turn, topic_data, stub, timeout)
        total_warnings += _warnings
        service_errors += _service_errors
        turns_validated += 1

        if total_warnings > max_warnings:
            logger.error(f'Maximum number of warnings exceeded ({total_warnings} > {max_warnings}), aborting!')
            sys.exit(255)

        if service_errors > 0 and strict:
            logger.error('Validation service errors encountered and strict mode enabled')
            sys.exit(255)

    logger.info(f'Validation completed on {turns_validated}/{len(run.turns)} turns with {total_warnings} warnings, {service_errors} service errors')
    return turns_validated, service_errors, total_warnings

def validate(run_file_path: str, fileroot: str, max_warnings: int, skip_validation: bool, strict: bool, timeout: float) -> Tuple[int, int, int]:
    """
    Top level run validation method.

    Connects to the gRPC validator service, loads topic data, loads the run file,
    and then calls `validate_run` to perform the validation.
    """
    run_file_name = PurePath(run_file_path).name
    fileHandler = logging.FileHandler(filename=f'{run_file_name}.errlog')
    fileHandler.setFormatter(formatter)
    logger.addHandler(fileHandler)

    # only instantiate the gRPC service client if skip_validation is False
    validator_stub = None if skip_validation else get_stub()

    if strict and not skip_validation and validator_stub is None:
        logger.error('Failed to set up validation service and strict checking was requested')
        raise Exception('Failed to set up validation service and strict checking was requested')

    topics_dict = load_topic_data(f'{fileroot}/2023_test_topics.json')

    run = load_run_file(run_file_path)
    
    if len(run.turns) == 0:
        logger.warning('Loaded run file has 0 turns, not performing any validation!')
        return len(run.turns), -1, -1
   
    turns_validated, service_errors, total_warnings = validate_run(run, topics_dict, validator_stub, max_warnings, strict, timeout)

    return turns_validated, service_errors, total_warnings

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='iKAT TREC 2023 validator',
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument('path_to_run_file')
    ap.add_argument('-f', '--fileroot', help='Location of data files', default='../../data')
    ap.add_argument('-S', '--skip_passage_validation', help='Skip passage ID validation', action='store_true')
    ap.add_argument('-m', '--max_warnings', help='Maximum number of warnings to allow', type=int, default=25) 
    ap.add_argument('-s', '--strict', help='Abort if any passage validation service errors occur', action='store_true')
    ap.add_argument('-t', '--timeout', help='Set the gRPC timeout (secs) for contacting the validation service', default=GRPC_DEFAULT_TIMEOUT, type=float)
    args = ap.parse_args()

    validate(args.path_to_run_file, args.fileroot, args.max_warnings, args.skip_passage_validation, args.strict, args.timeout)
