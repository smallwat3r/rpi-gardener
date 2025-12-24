"""Poll DHT22 sensor for new data, and persist results in Sqlite.

The script will take care of initiating the local database if it does not
exists yet. Polling frequency is set to 2 seconds, we can't make it poll
faster as the DHT22 sensor is set-up to measure for new data every 2
seconds, else cache results would be returned.
"""
import asyncio

from adafruit_dht import DHT22
from board import D17

from rpi.dht.display import display
from rpi.dht.models import Measure, Reading, Unit
from rpi.dht.audit import audit_reading, start_worker
from rpi.lib.db import close_db, get_db, init_db
from rpi.lib.config import DHT22_BOUNDS, MeasureName
from rpi.lib.polling import PollingService
from rpi.lib.utils import utcnow
from rpi.logging import configure, get_logger

logger = get_logger("dht.polling")


class OutsideDHT22Bounds(RuntimeError):
    """Reading from DHT22 sensor is outside of allowed bounds."""


class DHTPollingService(PollingService[Reading]):
    """Polling service for the DHT22 temperature/humidity sensor."""

    def __init__(self) -> None:
        super().__init__(name="DHT22")
        self._dht: DHT22 | None = None
        self._reading = Reading(
            Measure(0.0, Unit.CELSIUS),
            Measure(0.0, Unit.PERCENT),
            utcnow(),
        )

    async def initialize(self) -> None:
        """Initialize DHT22 sensor and database."""
        await init_db()
        start_worker()
        display.clear()
        self._dht = DHT22(D17)

    async def cleanup(self) -> None:
        """Clean up DHT22 sensor, display, and database connection."""
        display.clear()
        if self._dht:
            self._dht.exit()
        await close_db()

    async def poll(self) -> Reading | None:
        """Poll the DHT22 sensor for new reading values."""
        if self._dht is None:
            return None

        # Run sync sensor reads in thread pool
        temperature = await asyncio.to_thread(lambda: self._dht.temperature)
        humidity = await asyncio.to_thread(lambda: self._dht.humidity)

        self._reading.temperature.value = temperature
        self._reading.humidity.value = humidity
        self._reading.recording_time = utcnow()

        logger.info("Read %s, %s", str(self._reading.temperature),
                    str(self._reading.humidity))
        display.render_reading(self._reading)
        return self._reading

    async def audit(self, reading: Reading) -> bool:
        """Audit the reading against thresholds and DHT22 bounds."""
        # Check DHT22 bounds
        for name in MeasureName:
            measure = getattr(reading, name).value
            bmin, bmax = DHT22_BOUNDS[name]
            if measure < bmin or measure > bmax:
                logger.error(
                    "%s reading outside bounds of DHT22 sensor: %s",
                    name.capitalize(), measure
                )
                return False

        # Check thresholds and potentially trigger notifications
        audit_reading(reading)
        return True

    async def persist(self, reading: Reading) -> None:
        """Persist the reading values into the database."""
        async with get_db() as db:
            await db.execute(
                "INSERT INTO reading (temperature, humidity, recording_time) VALUES (?, ?, ?)",
                (reading.temperature.value, reading.humidity.value,
                 reading.recording_time)
            )

    async def clear_old_records(self) -> None:
        """Clear historical data older than retention period."""
        cutoff = self.get_cutoff_time()
        async with get_db() as db:
            await db.execute("DELETE FROM reading WHERE recording_time < ?", (cutoff,))
            await db.execute("DELETE FROM pico_reading WHERE recording_time < ?", (cutoff,))

    def on_poll_error(self, error: Exception) -> None:
        """Handle DHT22-specific errors."""
        if isinstance(error, RuntimeError):
            # DHT library raises RuntimeError for transient sensor issues
            # (e.g., checksum failures, timing issues). Log and retry.
            logger.debug("DHT22 sensor read error: %s", error)
        else:
            super().on_poll_error(error)


def main() -> None:
    """Main entry point for the polling service."""
    configure()
    service = DHTPollingService()
    service.run()


if __name__ == "__main__":
    main()
