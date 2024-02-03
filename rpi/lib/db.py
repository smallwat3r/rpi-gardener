import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Callable, Self, TypeAlias

_DB_NAME = "dht.sqlite3"


@lru_cache
def _get_sql_template(filename: str) -> str:
    with open(Path(__file__).resolve().parent / "sql" / filename) as query:
        return query.read()


class Sql:
    def __init__(self, query: str) -> None:
        self.query = query

    @classmethod
    def from_file(cls, filename: str) -> Self:
        query = _get_sql_template(filename)
        return cls(query)


SqlRow: TypeAlias = dict[str, str | int | float]


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> SqlRow:
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row, strict=True)}


class Db:
    def __init__(self, row_factory: Callable | None = None) -> None:
        self.con = sqlite3.connect(_DB_NAME, autocommit=False, timeout=10)
        if row_factory:
            self.con.row_factory = row_factory
        self.cur = self.con.cursor()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args, **kwargs) -> None:
        self.con.close()

    def query(self, sql: Sql, *args) -> sqlite3.Cursor:
        return self.cur.execute(sql.query, *args)

    def commit(self, sql: Sql, *args) -> None:
        self.cur.execute(sql.query, *args)
        self.con.commit()
