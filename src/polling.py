"""Poll DHT22 sensor for new data, and persist results in Sqlite.

The script will take care of initiating the local database if it does not
exists yet. Polling frequency is set to 2 seconds, we can't make it poll
faster as the DHT22 sensor is set-up to measure for new data every 2
seconds, else cache results would be returned.
"""
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from time import sleep
from typing import Callable

from adafruit_dht import DHT22
from board import D2

from . import logging
from ._config import POLLING_FREQUENCY_SEC, THRESHOLD_RULES
from ._db import Db, Sql
from ._events import Event, queue
from ._worker import start_worker

logger = logging.getLogger("polling-service")

@dataclass(frozen=True)
class Reading:
    temperature: float
    humidity: float
    recording_time: datetime


def _init_db() -> None:
    with Db() as db:
        db.commit(Sql.from_file("init_table.sql"))


def _audit_reading(reading: Reading) -> None:
    for type_, rules in THRESHOLD_RULES.items():
        for rule in rules:
            comparator, threshold = rule
            value = getattr(reading, type_)
            if comparator(value, threshold):
                queue.enqueue(Event(threshold, value))


def alert_on_threshold(func: Callable[[DHT22], Reading]):
    def wrapper(*args, **kwargs) -> Reading:
        reading = func(*args, **kwargs)
        _audit_reading(reading)
        return reading
    return wrapper


@alert_on_threshold
def _poll(dht: DHT22) -> Reading:
    reading = Reading(dht.temperature, dht.humidity, datetime.now())
    logger.info("Read %sc, %s%%", reading.temperature, reading.humidity)
    return reading


def _persist(reading: Reading) -> None:
    with Db() as db:
        db.commit(Sql("INSERT INTO reading VALUES (?, ?, ?)"),
                  (reading.temperature, reading.humidity,
                   reading.recording_time))


def main() -> None:
    _init_db()
    dht = DHT22(D2)
    start_worker()
    while True:
        # the DHT library can sporadically raise RuntimeError exceptions
        # when it encounters an issue when reading the data. Ignore those
        # exceptions, as next tries should be successful.
        with suppress(RuntimeError):
            _persist(_poll(dht))
        sleep(POLLING_FREQUENCY_SEC)


if __name__ == "__main__":
    main()
