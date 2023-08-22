#!/bin/sh

echo "> Compiling protobufs"
mkdir -p compiled_protobufs

# compile protos
ls protocol_buffers | \
grep .proto | \
xargs python3 -m grpc_tools.protoc \
    --proto_path=protocol_buffers \
    --python_out=compiled_protobufs \
    --grpc_python_out=compiled_protobufs

echo "> Building passage ID database"
python3 passage_id_db.py files/ikat_2023_passages_hashes.tsv
