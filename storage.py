from contextlib import contextmanager
from os import PathLike
import sqlite3


DatabasePath = str | PathLike[str]


@contextmanager
def connect(path: DatabasePath):
    database = sqlite3.connect(path, isolation_level=None)
    try:
        database.execute('PRAGMA foreign_keys = ON')
        yield database
    finally:
        database.close()


@contextmanager
def write_transaction(database: sqlite3.Connection):
    database.execute('BEGIN IMMEDIATE')
    try:
        yield
        database.execute('COMMIT')
    except BaseException:
        if database.in_transaction:
            database.execute('ROLLBACK')
        raise


def is_row_id(value: object) -> bool:
    return type(value) is int and 0 < value <= (1 << 63) - 1
