import sqlite3
from contextlib import closing, suppress
from datetime import datetime
from time import sleep

from adafruit_dht import DHT22
from board import D2

from .lib import db, logging

logger = logging.getLogger("dht-sensor")


def _init_db_table() -> None:
    with closing(db()) as con:
        cur = con.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS "
                    "reading(temperature, humidity, recording_time)")
        con.commit()


def _read_data(dht: DHT22) -> None:
    t, h = dht.temperature, dht.humidity
    logger.info("temperature=%sc humidity=%s%%", t, h)
    with closing(db()) as con:
        cur = con.cursor()
        cur.execute("INSERT INTO reading VALUES (?, ?, ?)",
                    (t, h, datetime.now()))
        con.commit()


if __name__ == "__main__":
    dht = DHT22(D2)
    _init_db_table()
    while True:
        with suppress(RuntimeError):
            _read_data(dht)
        sleep(2)
