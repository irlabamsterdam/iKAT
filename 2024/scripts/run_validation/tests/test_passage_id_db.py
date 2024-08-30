import pathlib
import os

from passage_id_db import PassageIDDatabase

from conftest import SAMPLE_DB_COUNT

TEMP_FILE = "temp.sqlite3"


def test_create_empty_database(tmp_path: pathlib.PurePath):
    """
    Test that opening an empty file as a database will fail.
    """
    path = tmp_path / TEMP_FILE
    if os.path.exists(path):
        os.unlink(path)

    with PassageIDDatabase(str(path)) as hdb:
        assert hdb.open()
        assert os.path.exists(path)


def test_create_sample_database(sample_database):
    """
    Test that loading a sample database produces the expected rowcount.
    """
    assert sample_database.rowcount() == SAMPLE_DB_COUNT


def test_validation_all_valid(sample_database):
    """
    Test validating a small set of passage IDs against the sample database.
    """
    # should all be valid for the sample database
    valid_passage_ids = [
        "clueweb22-en0004-24-00788:3",
        "clueweb22-en0004-30-06847:2",
        "clueweb22-en0004-50-06631:20",
        "clueweb22-en0004-59-06126:16",
        "clueweb22-en0004-67-04151:9",
    ]
    results = sample_database.validate(valid_passage_ids)
    assert results == [True for x in valid_passage_ids]


def test_validation_all_invalid(sample_database):
    """
    Test validating a set of invalid IDs against the sample database.
    """
    # expected results is [True, False, False, True]
    valid_passage_ids = ["clueweb22-en0004-67-04151:9", "foo", "bar", "clueweb22-en0004-50-06631:20"]
    results = sample_database.validate(valid_passage_ids)
    assert results == [True, False, False, True]
