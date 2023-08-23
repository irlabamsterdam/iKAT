import argparse
import csv
import logging
import os
import sqlite3
import sys
from typing import List, Optional

import tqdm

# expected number of passages in the collection (=number of lines in the hashes .tsv file)
IKAT_PASSAGE_COUNT = 116838987

# default number of rows to insert into a single insert when building the database
DEFAULT_BATCH_SIZE = 20000

LOGLEVEL = logging.INFO

logger = logging.Logger(__file__)
logger.setLevel(LOGLEVEL)
# log to stdout and to file
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.addHandler(logging.FileHandler(__file__ + '.log'))

class PassageIDDatabase:

    TABLE_NAME = 'passage_ids'
    COL_NAME = 'id'

    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: Optional[sqlite3.Connection] = None

    def open(self) -> bool:
        """
        Open a database file at the location given by self.path. If there's an 
        existing file there it will be opened, otherwise a new file is created.
        """
        try:
            # using check_same_thread=False should be safe here because the
            # database is either going to be populated or used for reads, not
            # both at the same time
            self._conn = sqlite3.connect(self.path, check_same_thread=False)
        except sqlite3.Error as sqle:
            logger.error(f'Error initialising database: {sqle}')
            return False

        return True

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def populate(self, hash_file: str, batch_size: int, num_lines: int = IKAT_PASSAGE_COUNT) -> bool:
        """
        Populate the database from a .tsv file.

        Rows are expected to contain ClueWeb22-ID<tab>passage number<tab>passage hash.
        
        Inserts are done in transactions of batch_size rows.
        """

        if self._conn is None:
            raise Exception('Database connection has not been opened')

        # since we're (re)populating, (re)create the schema
        cur = self._conn.cursor()
        try:
            cur.execute(f'DROP TABLE IF EXISTS {PassageIDDatabase.TABLE_NAME}')
            cur.execute(f'CREATE TABLE {PassageIDDatabase.TABLE_NAME} ({PassageIDDatabase.COL_NAME} TEXT PRIMARY KEY NOT NULL)')
        except sqlite3.Error as sqle:
            logger.error(f'Error initialising database: {sqle}')
            return False

        # try to speed up the inserts a little:
        # - increase the default page cache size
        # - disable journaling
        # - disable synchronous writes
        # - store temporary data in memory
        cur.execute('PRAGMA cache_size = -500000')
        cur.execute('PRAGMA journal_mode = OFF')
        cur.execute('PRAGMA synchronous = OFF')
        cur.execute('PRAGMA temp_store = MEMORY')

        batch = []
        inserted = 0
        batch_count = 0
        with tqdm.tqdm(total=num_lines) as progress:
            with open(hash_file, 'r') as hf:
                rdr = csv.reader(hf, delimiter='\t')
                for row in rdr:
                    batch.append((f'{row[0]}:{row[1]}', ))

                    if len(batch) == batch_size:
                        cur.executemany(f'INSERT INTO {PassageIDDatabase.TABLE_NAME} VALUES (?)', batch)
                        progress.update(len(batch))
                        self._conn.commit()
                        inserted += len(batch)
                        batch_count += 1
                        batch = []

                # final partial batch
                cur.executemany(f'INSERT INTO {PassageIDDatabase.TABLE_NAME} VALUES (?)', batch)
                self._conn.commit()
                inserted += len(batch)
                logger.info(f'Inserted {inserted:9d} rows')
                progress.update(len(batch))

            logger.info(f'Database populated with {inserted} rows, vacuuming...')
            self._conn.execute('VACUUM')
            logger.info('Database population complete!')
        return True

    def validate(self, ids: List[str]) -> List[bool]:
        """
        Check a list of passage IDs are in the database.

        Expects a list of passage IDs in the standard ClueWeb22-ID:passage number format.

        Returns a list of bools the same size as the input list indicating if each ID is valid/invalid.
        """
        if self._conn is None:
            raise Exception('Database connection has not been opened')

        results = []
        cur = self._conn.cursor()
        for id in ids:
            cur.execute(f'SELECT {PassageIDDatabase.COL_NAME} FROM {PassageIDDatabase.TABLE_NAME} \
                    WHERE {PassageIDDatabase.COL_NAME} = ?', (id, ))
            result = cur.fetchone()
            results.append(False if result is None else True)
            logger.debug(f'Validate {id} = {result is not None}')

        cur.close()
        return results

    def close(self) -> bool:
        """
        Close the database connection if it's currently open.
        """
        if self._conn is not None:
            self._conn.commit()
            self._conn.close()
        return True

    def rowcount(self) -> int:
        """
        Returns the number of rows in the database.
        """
        if self._conn is None:
            raise Exception('Database connection has not been opened')

        cur = self._conn.cursor()
        try:
            cur.execute(f'SELECT COUNT({PassageIDDatabase.COL_NAME}) FROM {PassageIDDatabase.TABLE_NAME}')
        except sqlite3.OperationalError as sqle:
            logger.error(f'Failed to get row count: {sqle}')
            return -1
        return cur.fetchone()[0]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('hash_file')
    parser.add_argument('-b', '--batch_size', help='Number of rows in each insert transaction', type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    if not os.path.exists(args.hash_file):
        print(f'Error: {args.hash_file} does not exist!')
        sys.exit(255)

    # create database in same location as the input, replacing the extension with .sqlite3
    db_name, db_ext = os.path.splitext(args.hash_file)
    db_name = db_name + '.sqlite3'
    print(f'Creating database at {db_name}')

    if os.path.exists(db_name):
        os.unlink(db_name)

    with PassageIDDatabase(db_name) as hdb:
        if not hdb.populate(args.hash_file, args.batch_size):
            print('Error: failed to populate the database!')
            sys.exit(255)

        print(f'Database populated, row count is {hdb.rowcount()}')
