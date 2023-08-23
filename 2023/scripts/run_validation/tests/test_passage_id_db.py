import pathlib
import os

from passage_id_db import PassageIDDatabase

TEMP_FILE = 'temp.sqlite3'

def test_create_empty_database(tmp_path: pathlib.PurePath):
    path = tmp_path / TEMP_FILE
    if os.path.exists(path):
        os.unlink(path)

    with PassageIDDatabase(str(path)) as hdb:
        assert hdb.open()
        assert os.path.exists(path)

def test_create_sample_database(sample_database):
    assert sample_database.rowcount() == 10000

def test_validation_all_valid(sample_database):
    # should all be valid for the sample database
    valid_passage_ids = [
        'clueweb22-en0004-24-00788:3',
        'clueweb22-en0004-30-06847:2',
        'clueweb22-en0004-50-06631:20',
        'clueweb22-en0004-59-06126:16',
        'clueweb22-en0004-67-04151:9',
    ]
    results = sample_database.validate(valid_passage_ids)
    assert results == [True for x in valid_passage_ids]

def test_validation_all_invalid(sample_database):
    # expected results is [True, False, False, True]
    valid_passage_ids = ['clueweb22-en0004-67-04151:9', 'foo', 'bar', 'clueweb22-en0004-50-06631:20']
    results = sample_database.validate(valid_passage_ids)
    assert results == [True, False, False, True]

