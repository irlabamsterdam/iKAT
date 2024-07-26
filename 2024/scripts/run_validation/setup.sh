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

hash_db="files/ikat_2023_passages_hashes.sqlite3"
if [ -f "${hash_db}" ]
then
    echo "> Hash database already exists. Delete ${hash_db} and rerun setup.sh to regenerate it if needed."
else
    echo "> Building passage ID database ${hash_db}"
    python3 passage_id_db.py files/ikat_2023_passages_hashes.tsv
fi

