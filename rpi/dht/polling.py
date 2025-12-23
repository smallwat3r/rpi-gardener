"""Poll DHT22 sensor for new data, and persist results in Sqlite.

The script will take care of initiating the local database if it does not
exists yet. Polling frequency is set to 2 seconds, we can't make it poll
faster as the DHT22 sensor is set-up to measure for new data every 2
seconds, else cache results would be returned.
"""
import signal
from datetime import timedelta
from time import sleep
from types import FrameType

from adafruit_dht import DHT22
from board import D17
from sqlitey import Sql

from rpi import logging
from rpi.dht.service import audit_reading, start_worker
from rpi.dht.display import display
from rpi.lib.config import (
    CLEANUP_INTERVAL_CYCLES,
    CLEANUP_RETENTION_DAYS,
    DHT22_BOUNDS,
    POLLING_FREQUENCY_SEC,
    MeasureName,
    db_with_config,
)
from rpi.lib.db import init_db
from rpi.lib.utils import utcnow
from rpi.dht.models import Measure, Reading, Unit

logger = logging.getLogger("polling-service")

# Flag to signal graceful shutdown
_shutdown_requested = False


class _OutsideDHT22Bounds(RuntimeError):
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
            raise _OutsideDHT22Bounds()
    return reading


def _poll(dht: DHT22, reading: Reading) -> Reading:
    """Poll the DHT22 sensor for new reading values."""
    reading.temperature.value = dht.temperature
    reading.humidity.value = dht.humidity
    reading.recording_time = utcnow()
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


def _clear_old_records() -> None:
    """Clear historical data older than CLEANUP_RETENTION_DAYS."""
    logger.info("Clearing historical data older than %d days...",
                CLEANUP_RETENTION_DAYS)
    cutoff = utcnow() - timedelta(days=CLEANUP_RETENTION_DAYS)
    with db_with_config() as db:
        db.commit(Sql.raw("DELETE FROM reading WHERE recording_time < ?"),
                  (cutoff,))
        db.commit(Sql.raw("DELETE FROM pico_reading WHERE recording_time < ?"),
                  (cutoff,))


def _handle_shutdown(signum: int, frame: FrameType | None) -> None:
    """Handle shutdown signals gracefully."""
    global _shutdown_requested
    signal_name = signal.Signals(signum).name
    logger.info("Received %s, initiating graceful shutdown...", signal_name)
    _shutdown_requested = True


def _setup_signal_handlers() -> None:
    """Register signal handlers for graceful shutdown."""
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)


def _cleanup(dht: DHT22) -> None:
    """Clean up resources before exit."""
    logger.info("Cleaning up resources...")
    display.clear()
    dht.exit()
    logger.info("Shutdown complete")


def main() -> None:
    """Main entry point for the polling service."""
    _setup_signal_handlers()
    init_db()
    start_worker()
    reading = Reading(
        Measure(0.0, Unit.CELSIUS),
        Measure(0.0, Unit.PERCENT),
        utcnow(),
    )
    display.clear()
    dht = DHT22(D17)

    logger.info("Polling service started")

    poll_count = 0
    try:
        while not _shutdown_requested:
            if poll_count % CLEANUP_INTERVAL_CYCLES == 0:
                _clear_old_records()
            try:
                _persist(_audit(_poll(dht, reading)))
            except _OutsideDHT22Bounds:
                # Reading was outside valid sensor bounds, skip and retry
                logger.debug("Skipping reading outside DHT22 bounds")
            except RuntimeError as e:
                # DHT library raises RuntimeError for transient sensor issues
                # (e.g., checksum failures, timing issues). Log and retry.
                logger.debug("DHT22 sensor read error: %s", e)
            poll_count += 1
            sleep(POLLING_FREQUENCY_SEC)
    finally:
        _cleanup(dht)


if __name__ == "__main__":
    main()
