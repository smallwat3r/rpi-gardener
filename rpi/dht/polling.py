"""Poll DHT22 sensor for new data, and persist results in Sqlite.

The script will take care of initiating the local database if it does not
exists yet. Polling frequency is set to 2 seconds, we can't make it poll
faster as the DHT22 sensor is set-up to measure for new data every 2
seconds, else cache results would be returned.
"""
from contextlib import suppress
from datetime import datetime
from random import randint
from sqlite3 import OperationalError
from time import sleep

from adafruit_dht import DHT22
from board import D17
from sqlitey import Sql

from rpi import logging
from rpi.dht.service import audit_reading, display, start_worker
from rpi.lib.config import (
    DHT22_BOUNDS,
    POLLING_FREQUENCY_SEC,
    MeasureName,
    db_with_config,
)
from rpi.lib.reading import Measure, Reading, Unit

logger = logging.getLogger("polling-service")


def _init_db() -> None:
    """Init database scripts."""
    with db_with_config() as db:
        db.executescript(Sql.template("init_reading_table.sql"))
        with suppress(OperationalError):
            db.executescript(Sql.template("idx_reading.sql"))
        db.executescript(Sql.template("init_pico_reading_table.sql"))
        with suppress(OperationalError):
            db.executescript(Sql.template("idx_pico_reading.sql"))


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


def _poll(dht: DHT22, reading: Reading) -> Reading:
    """Poll the DHT22 sensor for new reading values."""
    reading.temperature.value = dht.temperature
    reading.humidity.value = dht.humidity
    reading.recording_time = datetime.utcnow()
    logger.info("Read %s, %s", str(reading.temperature),
                str(reading.humidity))
    display.render_reading(reading)
    return reading


def _audit(reading: Reading) -> Reading:
    """Audit the reading."""
    _check_dht_boundaries(reading)
    audit_reading(reading)
    return reading


def _persist(reading: Reading) -> None:
    """Persist the reading values into the database."""
    with db_with_config() as db:
        db.commit(Sql.raw("INSERT INTO reading VALUES (?, ?, ?)"),
                  (reading.temperature.value, reading.humidity.value,
                   reading.recording_time))


def _randomly_clear_records() -> None:
    """Once in a while, clear historical data."""
    if randint(1, 10) != 1:
        return
    logger.info("Clearing historical data...")
    with db_with_config() as db:
        db.commit(
            Sql.raw("DELETE FROM reading "
                    "WHERE recording_time < datetime('now', '-3 days')"))


def main() -> None:
    _init_db()
    start_worker()
    reading = Reading(
        Measure(0.0, Unit.CELCIUS),
        Measure(0.0, Unit.PERCENT),
        datetime.utcnow(),
    )
    display.clear()
    dht = DHT22(D17)
    while True:
        _randomly_clear_records()
        # the DHT library can sporadically raise RuntimeError exceptions
        # when it encounters an issue when reading the data. Ignore those
        # exceptions, as next tries should be successful.
        # some custom exceptions from the polling code also use RuntimeError
        # as their base class, so they can fall into the same suppression
        # process (due to incorrect readings from the DHT sensor).
        with suppress(RuntimeError):
            _persist(_audit(_poll(dht, reading)))
        sleep(POLLING_FREQUENCY_SEC)


if __name__ == "__main__":
    main()
