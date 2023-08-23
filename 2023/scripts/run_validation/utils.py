import sys

from logging import Logger
from typing import Any, List

sys.path.append('./compiled_protobufs')
from passage_validator_pb2 import PassageValidationRequest
from passage_validator_pb2_grpc import PassageValidatorStub
from run_pb2 import Turn, PassageProvenance, PTKBProvenance, Response

def check_response(response: Response, logger: Logger, previous_rank: int, turn_id: str) -> int:
    """
    Validate a Response within a Turn.

    This checks if the Response:
     - has a rank > 0
     - has a rank > the previous rank
     - has a non-empty response text

    Return value is the number of warnings generated.
    """
    new_warnings = 0 

    # the rank should be >= 1
    if response.rank == 0:
        logger.warning(f"Response rank for turn {turn_id} is missing or equal to 0")
        new_warnings += 1

    # rank values should increase with successive responses
    if response.rank <= previous_rank:
        logger.warning(f"Current rank {response.rank} is less than or equal to previous rank {previous_rank} for turn {turn_id}. Provenance ranking may not be in descending order")
        new_warnings += 1

    # the response text shouldn't be empty
    if len(response.text) == 0:
        logger.warning(f"Response text for turn {turn_id} is missing")
        new_warnings += 1
    
    return new_warnings

def check_passage_provenance(prev_score: float, provenance: PassageProvenance, logger: Logger, turn_id: str) -> int:
    """
    Validate a PassageProvenance entry.

    This checks if the PassageProvenance:
     - has a score below that of the previous entry
     - has a 'clueweb22-' prefix on the passage ID
     - has a single colon in the passage ID

    Return value is the number of warnings generated.
    """
    new_warnings = 0

    # the scores should decrease with each entry
    if provenance.score > prev_score:
        logger.warning(f'Provenance entry with ID {provenance.id} in turn {turn_id} has a greater score than the previous passage ({provenance.score} > {prev_score}. Ranking order for turn {turn_id} not correct')
        new_warnings += 1

    # check the passage ID seems sensible
    if not provenance.id.startswith('clueweb22-'):
        logger.warning(f'{provenance.id} does not have a "clueweb22-" prefix, may be invalid')
        new_warnings += 1

    if len(provenance.id.split(':')) != 2:
        logger.warning(f'{provenance.id} seems to be formatted incorrectly (missing/extra colons?)')
        new_warnings += 1

    return new_warnings

def check_ptkb_provenance(ptkb_prov: PTKBProvenance, turn: Turn, ptkbs: dict[str, Any], prev_score: float, logger: Logger) -> int:
    """
    Validate a PTKBProvenance entry.

    This checks if the PTKBProvenance:
     - has a non-empty PTKB ID
     - has a PTKB ID that appears in the topics file
     - has PTKB text that matches the corresponding entry in the topics file
     - has a score that is greater than the previous entry

    Return value is the number of warnings generated.
    """
    new_warnings = 0

    if len(ptkb_prov.id) == 0:
        logger.error(f'A PTKB provenance ID in turn {turn.turn_id} is empty')
        sys.exit(255)

    if ptkb_prov.id not in ptkbs:
        logger.error(f'PTKB provenance with ID {ptkb_prov.id} in turn {turn.turn_id} is invalid')
        sys.exit(255)

    if ptkb_prov.text != ptkbs[ptkb_prov.id]:
        logger.error(f'PTKB provenance with ID {ptkb_prov.id} in turn {turn.turn_id} has a text mismatch')
        sys.exit(255)

    if ptkb_prov.score > prev_score:
        logger.warning(f'PTKB provenance with ID {ptkb_prov.id} in turn {turn.turn_id} has a score greater than the previous entry, ordering may be incorrect')
        new_warnings += 1

    return new_warnings

def validate_passages(passage_validation_client: PassageValidatorStub, logger: Logger, turn: Turn, timeout: float) -> int:
    """
    Validate passage IDs using the gRPC validation service.

    Constructs a list of all the unique passage IDs referenced in the given Turn,
    and packages them as a PassageValidationRequest. The request is sent to the 
    validation service, and the result is checked for any invalid IDs.

    Return values is the number of passage IDs found to be invalid. 
    """
    passage_validation_request = PassageValidationRequest()

    # build a list of passage IDs, filtering out duplicates
    passage_ids_set = set()
    for response in turn.responses:
        for provenance in response.passage_provenance:
            passage_ids_set.add(provenance.id)
    passage_ids: List[str] = list(passage_ids_set)

    # call the validator service
    passage_validation_request.passage_ids.MergeFrom(passage_ids)
    passage_validation_result = passage_validation_client.validate_passages(passage_validation_request, timeout=timeout)

    # check if any passage IDs failed to validate
    invalid_indexes = [i for i, passage_validation in enumerate(passage_validation_result.passage_validations) if not passage_validation.is_valid]
    for index in invalid_indexes:
        logger.warning(f"Provenance with ID {passage_ids[index]} does not exist in the passage collection")

    return len(invalid_indexes)
