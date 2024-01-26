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
from board import D17

from . import logging
from ._config import POLLING_FREQUENCY_SEC, THRESHOLD_RULES
from ._db import Db, Sql
from ._display import display
from ._events import Event, queue
from ._reading import Measure, Reading, State, Unit
from ._worker import start_worker

logger = logging.getLogger("polling-service")


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
            measure = getattr(reading, name)
            if comparator(measure.value, threshold):
                setattr(tracker, name, State.IN_ALERT)
                if not getattr(reading, name).state == State.IN_ALERT:
                    queue.enqueue(Event(measure, threshold,
                                        reading.recording_time))
                break
        getattr(reading, name).state = getattr(tracker, name)


def alert_on_threshold(func: Callable[[DHT22], Reading]) -> Reading:
    def wrapper(*args, **kwargs) -> Reading:
        reading = func(*args, **kwargs)
        _audit_reading(reading)
        return reading
    return wrapper


@alert_on_threshold
def _poll(dht: DHT22, reading: Reading) -> Reading:
    reading.temperature.value = dht.temperature
    reading.humidity.value = dht.humidity
    reading.recording_time = datetime.now()
    display.render_reading(reading)
    logger.info("Read %s, %s", str(reading.temperature),
                str(reading.humidity))
    return reading


def _persist(reading: Reading) -> None:
    with Db() as db:
        db.commit(Sql("INSERT INTO reading VALUES (?, ?, ?)"),
                  (reading.temperature.value, reading.humidity.value,
                   reading.recording_time))


def main() -> None:
    _init_db()
    start_worker()
    reading = Reading(Measure(0.0, Unit.CELCIUS),
                      Measure(0.0, Unit.PERCENT),
                      datetime.now())
    display.clear()
    dht = DHT22(D17)
    while True:
        # the DHT library can sporadically raise RuntimeError exceptions
        # when it encounters an issue when reading the data. Ignore those
        # exceptions, as next tries should be successful.
        with suppress(RuntimeError):
            _persist(_poll(dht, reading))
        sleep(POLLING_FREQUENCY_SEC)


if __name__ == "__main__":
    main()
