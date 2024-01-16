import logging

import sqlite3

logging.basicConfig(format="%(asctime)s %(levelname)s - %(message)s",
                    level=logging.INFO)


def db() -> sqlite3.Connection:
    return sqlite3.connect("dht.db", autocommit=False)
