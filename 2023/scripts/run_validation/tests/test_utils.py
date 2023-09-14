import pytest

from compiled_protobufs.passage_validator_pb2 import PassageValidationRequest
from compiled_protobufs.run_pb2 import PassageProvenance
from utils import validate_passages
from main import GRPC_DEFAULT_TIMEOUT, validate_turn, load_topic_data

def build_request(ids):
    request = PassageValidationRequest()
    request.passage_ids.MergeFrom(ids)
    return request

def get_invalid_indices(response):
    return [i for i, pv in enumerate(response.passage_validations) if not pv.is_valid]

def test_validate_passages(grpc_stub_full, test_logger, sample_turn):
    """
    Test that a sample turn from the baseline run file validates as expected.
    """
    assert(validate_passages(grpc_stub_full, test_logger, sample_turn, GRPC_DEFAULT_TIMEOUT) == 0)

def test_validate_too_many_passages(grpc_stub_full, sample_turn, topic_data_file):
    """
    Test that validation generates warnings when too many passages appear in a response.
    """

    # add extra passages to each response of the sample turn
    num_responses = len(sample_turn.responses)
    passages = []
    for i in range(1010):
        pprov = PassageProvenance()
        pprov.id = 'clueweb22-en0004-24-00788:3'
        pprov.score = -1 - (i / 1000.0)
        pprov.used = True
        pprov.text = '...'
        passages.append(pprov)

    for i in range(num_responses):
        sample_turn.responses[i].passage_provenance.MergeFrom(passages)

    topic_data = load_topic_data(topic_data_file)
    topic_id = sample_turn.turn_id.split('_')[0]

    # this should produce 2 warnings per response due to the number of passages listed being >1k
    # and not having any PTKB entries
    warning_count, service_errors = validate_turn(sample_turn, topic_data[topic_id], grpc_stub_full, GRPC_DEFAULT_TIMEOUT)
    assert(warning_count == len(sample_turn.responses) * 2)
    assert(service_errors == 0)

def test_all_invalid_ids(grpc_stub_test):
    """
    Test that validate_passages correctly marks invalid IDs.
    """
    response = grpc_stub_test.validate_passages(build_request(set(['foo', 'bar', 'foobar', 'barfoo'])))

    assert(get_invalid_indices(response) == [0, 1, 2, 3])

def test_all_valid(grpc_stub_test, sample_ids):
    """
    Test that validate_passages validates a set of valid IDs.

    The IDs are taken from a file containing the first 10k lines of the full passage hash file.
    """
    valid_ids = set(sample_ids[0:len(sample_ids):100])
    response = grpc_stub_test.validate_passages(build_request(valid_ids))

    assert(len(get_invalid_indices(response)) == 0)

def test_mixed_ids(grpc_stub_test, sample_ids):
    """
    Test that validate_passages correctly validates a mix of valid/invalid IDs.
    """
    mixed_ids = set(sample_ids[0:len(sample_ids):100])
    invalid_ids = ['foo', 'bar', 'foobar', 'barfoo', '', sample_ids[0].replace(':', '|')]
    mixed_ids.update(invalid_ids)

    response = grpc_stub_test.validate_passages(build_request(mixed_ids))

    assert(len(get_invalid_indices(response)) == len(invalid_ids))

def test_empty(grpc_stub_test):
    """
    Test that validate passages doesn't fail if given an empty set of IDs.
    """
    response = grpc_stub_test.validate_passages(build_request([]))
    assert(len(get_invalid_indices(response)) == 0)
