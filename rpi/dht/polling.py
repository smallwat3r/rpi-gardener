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

from rpi import logging
from rpi.dht._display import display
from rpi.dht._worker import start_worker
from rpi.lib.config import (
    DHT22_BOUNDS,
    POLLING_FREQUENCY_SEC,
    THRESHOLD_RULES,
    MeasureName,
)
from rpi.lib.db import Db, Sql
from rpi.lib.events import Event, queue
from rpi.lib.reading import Measure, Reading, State, Unit

logger = logging.getLogger("polling-service")


def _init_db() -> None:
    with Db() as db:
        db.commit(Sql.from_file("init_reading_table.sql"))
        db.commit(Sql.from_file("init_pico_reading_table.sql"))


@dataclass
class _StateTracker:
    temperature: State = State.OK
    humidity: State = State.OK


def _audit_reading(reading: Reading) -> None:
    """Audit reading value, and enqueue notification events."""
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


class OutsideDHT22Bounds(RuntimeError):
    """Reading from DHT22 sensor is outside of allowed bounds."""


def _check_dht_boundaries(reading: Reading) -> Reading:
    """Ensure the readings from the sensor are sane.

    The DHT22 sensor only allows specific bounds for temperature and humidity
    readings. Temperature cannot be measured outside of the -40 to 80 degree
    celsius range. Humidity cannot be measured outside of 0-100% range.

    If the sensor were to record a reading outside of these bounds, something
    bad has happened, and the reading would need to be retried.
    """
    for name in MeasureName:
        measure = getattr(reading, name).value
        bmin, bmax = DHT22_BOUNDS[name]
        if measure < bmin or measure > bmax:
            logger.error("%s reading outside bounds of DHT22 sensor: %s",
                         name.capitalize(), str(reading.temperature))
            raise OutsideDHT22Bounds()
    return reading


def after_run_hook(func: Callable[[DHT22], Reading]) -> Reading:
    """Hook to run after polling."""
    def wrapper(*args, **kwargs) -> Reading:
        reading = func(*args, **kwargs)
        _check_dht_boundaries(reading)
        _audit_reading(reading)
        return reading
    return wrapper


@after_run_hook
def _poll(dht: DHT22, reading: Reading) -> Reading:
    """Poll the DHT22 sensor for new reading values."""
    reading.temperature.value = dht.temperature
    reading.humidity.value = dht.humidity
    reading.recording_time = datetime.now()
    logger.info("Read %s, %s", str(reading.temperature),
                str(reading.humidity))
    display.render_reading(reading)
    return reading


def _persist(reading: Reading) -> None:
    """Persist the reading values into the database."""
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
        # some custom exceptions from the polling code also use RuntimeError
        # as their base class, so they can fall into the same suppression
        # process (due to incorrect readings from the DHT sensor).
        with suppress(RuntimeError):
            _persist(_poll(dht, reading))
        sleep(POLLING_FREQUENCY_SEC)


if __name__ == "__main__":
    main()
