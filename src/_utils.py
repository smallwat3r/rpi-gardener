import logging
import sqlite3
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Self

logging.basicConfig(format="%(asctime)s %(levelname)s - %(message)s",
                    level=logging.INFO)


@lru_cache
def _get_sql_template(filename: str) -> str:
    with open(Path(__file__).resolve().parent / "sql" / filename) as query:
        return query.read()


class Db:
    def __init__(self) -> None:
        self.con = sqlite3.connect("dht.db", autocommit=False)
        # renders the rows as Python native dictionaries, very useful to
        # render the data directly in the frontend.
        self.con.row_factory = lambda c, r: dict(
            zip([col[0] for col in c.description], r))
        self.cur = self.con.cursor()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args, **kwargs) -> None:
        self.con.close()

    def _execute(self, filename: str, *args) -> sqlite3.Cursor:
        return self.cur.execute(_get_sql_template(filename), *args)

    def query(self, filename: str, *args) -> sqlite3.Cursor:
        return self._execute(filename, *args)

    def commit(self, filename: str, *args) -> None:
        self._execute(filename, *args)
        self.con.commit()


@dataclass(frozen=True)
class Reading:
    temperature: float
    humidity: float
    recording_time: datetime
