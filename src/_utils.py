import logging
import sqlite3
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Self, TypeAlias

logging.basicConfig(format="%(asctime)s %(levelname)s - %(message)s",
                    level=logging.INFO)


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


def _dict_factory(cursor: sqlite3.Cursor, row: tuple) -> SqlRow:
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row, strict=True)}


class Db:
    def __init__(self, dict_row_factory: bool = False) -> None:
        self.con = sqlite3.connect("dht.db", autocommit=False)
        if dict_row_factory:
            self.con.row_factory = _dict_factory
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


@dataclass(frozen=True)
class Reading:
    temperature: float
    humidity: float
    recording_time: datetime
