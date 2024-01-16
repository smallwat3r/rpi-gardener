import sqlite3
import logging
from contextlib import suppress
from datetime import datetime
from time import sleep

from adafruit_dht import DHT22
from board import D2

logging.basicConfig(format="%(asctime)s %(levelname)s - %(message)s",
                    level=logging.INFO)
logger = logging.getLogger("dht")


def _init_db_table(con: sqlite3.Connection) -> None:
    con.execute("CREATE TABLE IF NOT EXISTS "
                "reading(temperature, humidity, recording_time)")


def _read_data(dht: DHT22, con: sqlite3.Connection) -> None:
    with suppress(RuntimeError):
        t, h = dht.temperature, dht.humidity
        con.execute("INSERT INTO reading VALUES (?, ?, ?)",
                    (t, h, datetime.now()))
        logger.info("temperature=%sc humidity=%s%%", t, h)
        con.commit()
    sleep(2)


if __name__ == "__main__":
    con = sqlite3.connect("dht.db")
    dht = DHT22(D2)
    _init_db_table(con)
    while True:
        _read_data(dht, con)
