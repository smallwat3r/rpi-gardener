"""Poll DHT22 sensor for new data, and persist results in Sqlite.

The script will take care of initiating the local database if it does not
exists yet. Polling frequency is set to 2 seconds, we can't make it poll
faster as the DHT22 sensor is set-up to measure for new data every 2
seconds, else cache results would be returned.
"""
from contextlib import suppress
from datetime import datetime
from time import sleep

from adafruit_dht import DHT22
from board import D2

from ._config import POLLING_FREQUENCY_SEC
from ._utils import Db, Reading, logging

logger = logging.getLogger("dht-polling-service")


def _init_db() -> None:
    with Db() as db:
        db.execute("init_table.sql")


def _poll(dht: DHT22) -> Reading:
    reading = Reading(dht.temperature, dht.humidity, datetime.now())
    logger.info("temperature=%sc humidity=%s%%",
                reading.temperature, reading.humidity)
    return reading


def _persist(reading: Reading) -> None:
    with Db() as db:
        db.execute("feed_table.sql", (reading.temperature, reading.humidity,
                                      reading.recording_time))


def main() -> None:
    dht = DHT22(D2)
    _init_db()
    while True:
        # the DHT library can sporadically raise RuntimeError exceptions
        # when it encounters an issue when reading the data. Ignore those
        # exceptions, as next tries should be successful.
        with suppress(RuntimeError):
            _persist(_poll(dht))
        sleep(POLLING_FREQUENCY_SEC)


if __name__ == "__main__":
    main()
