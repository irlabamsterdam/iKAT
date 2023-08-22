import sys

import grpc

from passage_id_db import PassageIDDatabase

sys.path.append('./compiled_protobufs')
from passage_validator_pb2 import PassageValidation, PassageValidationRequest, PassageValidationResult
from passage_validator_pb2_grpc import PassageValidatorServicer

class PassageValidator(PassageValidatorServicer):

    def __init__(self, db_path: str, expected_rows: int) -> None:
        self.db = PassageIDDatabase(db_path)
        if not self.db.open():
            print('Error: failed to open database, service cannot start!')
            sys.exit(255)

        if expected_rows > 0 and self.db.rowcount() != expected_rows:
            print(f'Error: Database row count of {self.db.rowcount()} vs expected {expected_rows}, invalid path?')
            sys.exit(255)

        print('>> Service ready')

    def validate_passages(self, request: PassageValidationRequest, context: grpc.ServicerContext) -> PassageValidationResult:
        """
        Takes in a list of passage ids and checks if they appear in the database
        """
        passage_validation_result = PassageValidationResult()

        # query database with the set of passage IDs and return a list of bools
        # indicate valid/invalid for each ID
        validation_results = self.db.validate(request.passage_ids)

        for result in validation_results:
            passage_validation = PassageValidation()
            passage_validation.is_valid = result
            passage_validation_result.passage_validations.append(passage_validation)

        return passage_validation_result
