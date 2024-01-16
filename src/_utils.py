import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Self

logging.basicConfig(format="%(asctime)s %(levelname)s - %(message)s",
                    level=logging.INFO)


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

    def fetchall(self, query: str, *args) -> dict[str, float | int]:
        return self.cur.execute(query, *args).fetchall()

    def execute(self, query: str, *args) -> None:
        self.cur.execute(query, *args).fetchone()
        self.con.commit()


@dataclass(frozen=True)
class Reading:
    temperature: float
    humidity: float
    recording_time: datetime
