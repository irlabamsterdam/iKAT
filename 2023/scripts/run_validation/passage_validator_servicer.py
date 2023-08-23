import argparse
import sys
from concurrent import futures

import grpc
from passage_id_db import IKAT_PASSAGE_COUNT
from passage_validator import PassageValidator as PassageValidatorServicer

sys.path.append("./compiled_protobufs")
from compiled_protobufs.passage_validator_pb2_grpc import add_PassageValidatorServicer_to_server


def serve(db_path: str, expected_rows: int) -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_PassageValidatorServicer_to_server(PassageValidatorServicer(db_path, expected_rows), server)

    server.add_insecure_port("[::]:8000")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('db_path', type=str, help='SQLite database path', default='./files/ikat_2023_passages_hashes.sqlite3')
    parser.add_argument('expected_rows', type=int, nargs='?', default=IKAT_PASSAGE_COUNT, help='Expected number of rows in the database (0 to skip checking)')
    args = parser.parse_args()
    serve(args.db_path, args.expected_rows)
