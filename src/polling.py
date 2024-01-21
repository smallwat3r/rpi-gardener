"""Poll DHT22 sensor for new data, and persist results in Sqlite.

The script will take care of initiating the local database if it does not
exists yet. Polling frequency is set to 2 seconds, we can't make it poll
faster as the DHT22 sensor is set-up to measure for new data every 2
seconds, else cache results would be returned.
"""
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from time import sleep
from typing import Callable

from adafruit_dht import DHT22
from board import D2

from . import logging
from ._config import POLLING_FREQUENCY_SEC, THRESHOLD_RULES, UNIT_MAPPING
from ._db import Db, Sql
from ._events import Event, queue
from ._worker import start_worker

logger = logging.getLogger("polling-service")


class State(Enum):
    OK = auto()
    IN_ALERT = auto()


@dataclass
class Measure:
    value: float
    state: State = State.OK


@dataclass
class Reading:
    temperature: Measure
    humidity: Measure
    recording_time: datetime


def _init_db() -> None:
    with Db() as db:
        db.commit(Sql.from_file("init_table.sql"))


@dataclass
class _StateTracker:
    temperature: State = State.OK
    humidity: State = State.OK


def _audit_reading(reading: Reading) -> None:
    tracker = _StateTracker()
    for name, rules in THRESHOLD_RULES.items():
        for rule in rules:
            comparator, threshold = rule
            value = getattr(reading, name).value
            if comparator(value, threshold):
                setattr(tracker, name, State.IN_ALERT)
                # only triggers notification if the reading is not already in
                # alert, to avoid polluting the user.
                if not getattr(reading, name).state == State.IN_ALERT:
                    queue.enqueue(Event(value, threshold, UNIT_MAPPING[name],
                                        reading.recording_time))
                # thresholds are either min or max, so once one has been
                # triggered, the reading name (temperature or humidity) must
                # be 'in alert', so we can break and move on.
                break
        # update the reading with the tracker state.
        getattr(reading, name).state = getattr(tracker, name)


def alert_on_threshold(func: Callable[[DHT22], Reading]) -> Reading:
    def wrapper(*args, **kwargs) -> Reading:
        reading = func(*args, **kwargs)
        _audit_reading(reading)
        return reading
    return wrapper


@alert_on_threshold
def _poll(dht: DHT22, reading: Reading) -> Reading:
    reading.temperature = Measure(dht.temperature)
    reading.humidity = Measure(dht.humidity)
    reading.recording_time = datetime.now()
    logger.info("Read %sc, %s%%", reading.temperature.value,
                reading.humidity.value)
    return reading


def _persist(reading: Reading) -> None:
    with Db() as db:
        db.commit(Sql("INSERT INTO reading VALUES (?, ?, ?)"),
                  (reading.temperature.value, reading.humidity.value,
                   reading.recording_time))


def main() -> None:
    _init_db()
    start_worker()
    reading = Reading(Measure(0.0), Measure(0.0), datetime.now())  # init
    dht = DHT22(D2)
    while True:
        # the DHT library can sporadically raise RuntimeError exceptions
        # when it encounters an issue when reading the data. Ignore those
        # exceptions, as next tries should be successful.
        with suppress(RuntimeError):
            _persist(_poll(dht, reading))
        sleep(POLLING_FREQUENCY_SEC)


if __name__ == "__main__":
    main()
