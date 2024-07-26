import argparse
import json
import logging
import os
import sys
from pathlib import PurePath
from typing import Any

import grpc
from google.protobuf.json_format import ParseDict

from utils import check_passage_provenance, check_ptkb_provenance, check_response, validate_passages

sys.path.append("./compiled_protobufs")
from passage_validator_pb2_grpc import PassageValidatorStub
from run_pb2 import Turn, iKATRun

# a default timeout for gRPC calls to the passage validator
GRPC_DEFAULT_TIMEOUT = 3.0

# the number of entries that should be parsed from the topics JSON file
EXPECTED_TOPIC_ENTRIES = 25

# the total number of turns that should appear in a run (and the topics JSON file)
EXPECTED_RUN_TURN_COUNT = 332

VALID_RUN_TYPES = set(["automatic", "manual", "only_response"])

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
streamHandler = logging.StreamHandler(sys.stdout)
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)


def get_stub(ip: str = "localhost", port: int = 8000) -> PassageValidatorStub | None:
    """
    Create a gRPC channel to the validator service and return the service stub.
    """
    try:
        passage_validation_channel = grpc.insecure_channel(f"{ip}:{port}")
        passage_validation_client = PassageValidatorStub(passage_validation_channel)
    except grpc.RpcError as rpce:
        logger.error(f"A gRPC error occurred connecting to the validator service: {rpce.code().name}")
        return None

    return passage_validation_client


def load_topic_data(path: str) -> dict[str, dict[str, Any]]:
    """
    Load the test topics JSON file.

    Returns the content as a dict.
    """
    if not os.path.exists(path):
        logger.error(f"Topics file {path} not found!")
        raise Exception(f"Topics file {path} not found!")

    try:
        topic_data = json.load(open(path, "r"))
    except Exception as e:
        logger.error(f"Failed to load topics JSON data from {path}, exception: {e}")
        sys.exit(255)

    # check that topics were loaded correctly
    if len(topic_data) != EXPECTED_TOPIC_ENTRIES:
        logger.error(
            f"Topics file not loaded correctly (found {len(topic_data)} entries, expected {EXPECTED_TOPIC_ENTRIES})"
        )
        sys.exit(255)

    total_turns = sum(len(topic_data[i]["turns"]) for i in range(len(topic_data)))
    if total_turns != EXPECTED_RUN_TURN_COUNT:
        logger.error(
            f"Topics file not loaded correctly (found {total_turns} turns, expected {EXPECTED_RUN_TURN_COUNT} turns)"
        )

    # build a dict of the topics with "number" as the key
    topics_dict = {d["number"]: d for d in topic_data}
    return topics_dict


def load_run_file(run_file_path: str) -> iKATRun:
    """
    Loads the selected run file.

    The file is first opened and parsed as JSON. A couple of simple checks
    for expected top-level fields like "run_name" and "run_type" are made.
    After that the content is passed to ParseDict to populate a protobuf
    iKATRun object. This should generate an exception if there are any
    unexpected/missing fields in the JSON data.

    Returns a populated iKATRun object (see protocol_buffers/run.proto).
    """
    # validate structure
    with open(run_file_path, "r", encoding="utf-8") as run_file:
        try:
            run = json.load(run_file)
            # check for expected attributes
            if "run_name" not in run or "run_type" not in run:
                raise Exception("Missing run_name/run_type entry")

            if "turns" not in run:
                raise Exception("Missing turns entry")

            run = ParseDict(run, iKATRun())
        except Exception as e:
            logger.error(f"Run file not in the right format ({e})")
            sys.exit(255)

    return run


def validate_turn(
    turn: Turn, ptkb_data: dict[str, Any], stub: PassageValidatorStub | None, timeout: float
) -> tuple[int, int]:
    """
    Validate a single turn from a run.

    Returns a 2-tuple of (number of warnings, number of service errors)
    """
    warning_count, service_errors = 0, 0

    logger.debug(f"Validating turn {turn.turn_id}")
    previous_rank = 0

    # will be None if skip_passage_validation was used
    if stub is not None:
        try:
            # if passage validation is enabled, this is where we make a gRPC call to the
            # validation service to perform the passage ID checks
            warning_count += validate_passages(stub, logger, turn, timeout)
        except grpc.RpcError as rpce:
            logger.warning(
                f"A gRPC error occurred when validating passages (name={rpce.code().name}, message={rpce.details()})"
            )
            service_errors += 1

    for i, response in enumerate(turn.responses):
        # check the response:
        warning_count += check_response(response, logger, previous_rank, turn.turn_id)

        previous_score = 1e9

        # check passage provenances
        for provenance in response.passage_provenance:
            warning_count += check_passage_provenance(previous_score, provenance, logger, turn.turn_id)
            previous_score = provenance.score

        passages_used = [p.used for p in response.passage_provenance if p.used]

        if len(passages_used) == 0:
            logger.warning(
                f'Turn {turn.turn_id}, response #{i} has no passages marked as "used"! The top 5 passages will be used as provenance by default'
            )
            warning_count += 1

        if len(response.passage_provenance) == 0:
            logger.warning(f"Turn {turn.turn_id} has a response with no passage provenances")
            warning_count += 1
        elif len(response.passage_provenance) > 1000:
            logger.warning(f"Turn {turn.turn_id} has a response with >1000 passages ({len(response.passage_provenance)})")
            warning_count += 1

        if len(response.ptkb_provenance) == 0:
            logger.warning(f"No PTKB provenances listed for a response in turn {turn.turn_id}!")
            warning_count += 1
            continue  # no point in doing the next block

        prev_ptkb_score = 1e9

        for ptkb_prov in response.ptkb_provenance:
            warning_count += check_ptkb_provenance(ptkb_prov, turn, ptkb_data, prev_ptkb_score, logger)
            prev_ptkb_score = ptkb_prov.score

    return warning_count, service_errors


def validate_all_turns(run: iKATRun, topics_dict: dict[str, dict[str, Any]]) -> dict[str, list[Turn]]:
    """
    Given a run file, verify the number of turns.

    This involves:
        1. Checking that the total number of turns matches the test topics file
        2. Checking that there are the correct number of turns for each topic

    To make subsequent topic-by-topic validation simpler, this will also pull out
    the list of individual turns for each topic and return those.
    """

    # we already know the number of turns in topics_dict is correct after checking
    # that in the load_topic_data method. so here we need to first check the number
    # of turns in the run matches that...

    if len(run.turns) != EXPECTED_RUN_TURN_COUNT:
        logger.error(f"The run contains {len(run.turns)} turns, but the test topics contain {EXPECTED_RUN_TURN_COUNT} turns")
        sys.exit(255)

    run_topics_dict: dict[str, list[Turn]] = {}
    for turn in run.turns:
        # check if the turn ID looks valid
        try:
            topic_id, turn_id = turn.turn_id.split("_")
            turn_id = int(turn_id)
        except Exception as e:
            logger.error(f'Failed to parse turn ID "{turn.turn_id}", exception was {e}')
            sys.exit(255)

        if topic_id not in run_topics_dict:
            run_topics_dict[topic_id] = []

        run_topics_dict[topic_id].append(turn)

    # check we have the expected number of topics from the run file
    if len(run_topics_dict) != EXPECTED_TOPIC_ENTRIES:
        logger.error(f"The run contains {len(run_topics_dict)} topics, the expected number is {EXPECTED_TOPIC_ENTRIES}")
        sys.exit(255)

    # check each topic has the expected number of turns, and that each
    # expected topic appears in the run
    for topic_id, topic_data in topics_dict.items():
        if topic_id not in run_topics_dict:
            logger.error(f"The topic {topic_id} does not appear in the run file")
            sys.exit(255)

        expected_turns = len(topic_data["turns"])
        actual_turns = len(run_topics_dict[topic_id])
        if expected_turns != actual_turns:
            logger.error(f"The topic {topic_id} should have {expected_turns} turns but actually has {actual_turns} turns")
            sys.exit(255)

    return run_topics_dict


def validate_run(
    run: iKATRun,
    topics_dict: dict[str, dict[str, Any]],
    stub: PassageValidatorStub | None,
    max_warnings: int,
    timeout: float,
) -> tuple[int, int, int]:
    """
    Validates a run turn-by-turn, recording warnings and errors.
    """
    total_warnings, service_errors = 0, 0
    turns_validated = 0

    if len(run.run_name) == 0:
        logger.warning("Run has an empty run_name field")
        total_warnings += 1
    if len(run.run_type) == 0:
        logger.warning("Run has an empty run_type field")
        total_warnings += 1
    if run.run_type not in VALID_RUN_TYPES:
        logger.warning("Run has an unrecognised type, should be one of {VALID_RUN_TYPES}")
        total_warnings += 1

    run_topics_dict = validate_all_turns(run, topics_dict)

    for topic_id, topic_data in run_topics_dict.items():
        for turn in topic_data:
            topic_id, turn_id = turn.turn_id.split("_")
            turn_id = int(turn_id)

            max_turn_id = len(topics_dict[topic_id]["turns"])
            if turn_id < 1 or turn_id > max_turn_id:
                logger.error(f"Turn {turn.turn_id} has an invalid turn ID {turn_id}, expected range: 1-{max_turn_id}")
                sys.exit(255)

            _warnings, _service_errors = validate_turn(turn, topics_dict[topic_id]["ptkb"], stub, timeout)
            total_warnings += _warnings
            service_errors += _service_errors
            turns_validated += 1

            if total_warnings > max_warnings:
                logger.error(f"Maximum number of warnings exceeded ({total_warnings} > {max_warnings}), aborting!")
                sys.exit(255)

            if service_errors > 0:
                # always abort if a passage ID validation error occurs
                logger.error("Validation service errors encountered")
                sys.exit(255)

    logger.info(
        f"Validation completed on {turns_validated}/{len(run.turns)} turns with {total_warnings} warnings, {service_errors} service errors"
    )
    return turns_validated, service_errors, total_warnings


def validate(
    run_file_path: str, fileroot: str, max_warnings: int, skip_validation: bool, timeout: float
) -> tuple[int, int, int]:
    """
    Top level run validation method.

    Connects to the gRPC validator service, loads topic data, loads the run file,
    and then calls `validate_run` to perform the validation.
    """
    run_file_name = PurePath(run_file_path).name
    fileHandler = logging.FileHandler(filename=f"{run_file_name}.errlog")
    fileHandler.setFormatter(formatter)
    logger.addHandler(fileHandler)

    # only instantiate the gRPC service client if skip_validation is False
    validator_stub = None if skip_validation else get_stub()

    if not skip_validation and validator_stub is None:
        logger.error("Failed to set up validation service")
        raise Exception("Failed to set up validation service")

    topics_dict = load_topic_data(f"{fileroot}/2023_test_topics.json")

    run = load_run_file(run_file_path)

    if len(run.turns) == 0:
        logger.error("Loaded run file has 0 turns, not performing any validation!")
        return len(run.turns), -1, -1

    turns_validated, service_errors, total_warnings = validate_run(run, topics_dict, validator_stub, max_warnings, timeout)

    return turns_validated, service_errors, total_warnings


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="iKAT TREC 2023 validator", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    _ = ap.add_argument("path_to_run_file")
    _ = ap.add_argument("-f", "--fileroot", help="Location of data files", default="../../data")
    _ = ap.add_argument("-S", "--skip_passage_validation", help="Skip passage ID validation", action="store_true")
    _ = ap.add_argument("-m", "--max_warnings", help="Maximum number of warnings to allow", type=int, default=2000)
    _ = ap.add_argument(
        "-t",
        "--timeout",
        help="Set the gRPC timeout (secs) for contacting the validation service",
        default=GRPC_DEFAULT_TIMEOUT,
        type=float,
    )
    args = ap.parse_args()

    _ = validate(args.path_to_run_file, args.fileroot, args.max_warnings, args.skip_passage_validation, args.timeout)
