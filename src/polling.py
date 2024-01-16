from contextlib import suppress
from datetime import datetime
from time import sleep

from adafruit_dht import DHT22
from board import D2

from ._utils import Db, Reading, logging

logger = logging.getLogger("dht-sensor-polling")


def _init_db() -> None:
    with Db() as db:
        db.execute("CREATE TABLE IF NOT EXISTS "
                   "reading(temperature, humidity, recording_time)")


def _poll(dht: DHT22) -> Reading:
    reading = Reading(dht.temperature, dht.humidity, datetime.now())
    logger.info("temperature=%sc humidity=%s%%",
                reading.temperature, reading.humidity)
    return reading


def _persist(reading: Reading) -> None:
    with Db() as db:
        db.execute("INSERT INTO reading VALUES (?, ?, ?)",
                   (reading.temperature,
                    reading.humidity,
                    reading.recording_time))


if __name__ == "__main__":
    dht = DHT22(D2)
    _init_db()
    while True:
        with suppress(RuntimeError):
            _persist(_poll(dht))
        sleep(2)
