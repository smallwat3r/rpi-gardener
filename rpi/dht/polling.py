"""Poll DHT22 sensor for new data, and persist results in Sqlite.

The script will take care of initiating the local database if it does not
exists yet. Polling frequency is set to 2 seconds, we can't make it poll
faster as the DHT22 sensor is set-up to measure for new data every 2
seconds, else cache results would be returned.
"""

import asyncio
from datetime import UTC, datetime
from typing import Protocol, override

from rpi.dht.audit import audit_reading
from rpi.dht.audit import init as init_audit
from rpi.dht.display import DisplayProtocol
from rpi.dht.models import Measure, Reading
from rpi.lib.config import DHT22_BOUNDS, MeasureName, Unit
from rpi.lib.db import close_db, get_db, init_db
from rpi.lib.eventbus import DHTReadingEvent, Topic, get_publisher
from rpi.lib.polling import PollingService
from rpi.logging import configure, get_logger

logger = get_logger("dht.polling")


class DHTSensor(Protocol):
    """Protocol for DHT sensor interface."""

    @property
    def temperature(self) -> float: ...

    @property
    def humidity(self) -> float: ...

    def exit(self) -> None: ...


class DHTPollingService(PollingService[Reading]):
    """Polling service for the DHT22 temperature/humidity sensor."""

    def __init__(self, sensor: DHTSensor, display: DisplayProtocol) -> None:
        super().__init__(name="DHT22")
        self._dht = sensor
        self._display = display
        self._reading = Reading(
            Measure(0.0, Unit.CELSIUS),
            Measure(0.0, Unit.PERCENT),
            datetime.now(UTC),
        )

    @override
    async def initialize(self) -> None:
        """Initialize database, audit worker, and event publisher."""
        await init_db()
        init_audit()
        self._publisher = get_publisher()
        self._publisher.connect()
        self._display.clear()

    @override
    async def cleanup(self) -> None:
        """Clean up DHT22 sensor, display, event publisher, and database."""
        self._display.clear()
        self._dht.exit()
        self._publisher.close()
        await close_db()

    @override
    async def poll(self) -> Reading | None:
        """Poll the DHT22 sensor for new reading values."""
        # Run sync sensor reads in thread pool
        temperature = await asyncio.to_thread(lambda: self._dht.temperature)
        humidity = await asyncio.to_thread(lambda: self._dht.humidity)

        self._reading.temperature.value = temperature
        self._reading.humidity.value = humidity
        self._reading.recording_time = datetime.now(UTC)

        logger.info(
            "Read %s, %s",
            str(self._reading.temperature),
            str(self._reading.humidity),
        )
        self._display.render_reading(self._reading)
        return self._reading

    @override
    async def audit(self, reading: Reading) -> bool:
        """Audit the reading against thresholds and DHT22 bounds."""
        # Check DHT22 bounds
        for name in MeasureName:
            measure = getattr(reading, name).value
            bmin, bmax = DHT22_BOUNDS[name]
            if measure < bmin or measure > bmax:
                logger.error(
                    "%s reading outside bounds of DHT22 sensor: %s",
                    name.capitalize(),
                    measure,
                )
                return False

        # Check thresholds and potentially trigger notifications
        await audit_reading(reading)
        return True

    @override
    async def persist(self, reading: Reading) -> None:
        """Persist the reading values into the database and publish event."""
        async with get_db() as db:
            await db.execute(
                "INSERT INTO reading (temperature, humidity, recording_time) VALUES (?, ?, ?)",
                (
                    reading.temperature.value,
                    reading.humidity.value,
                    reading.recording_time,
                ),
            )

        # Publish to event bus for real-time WebSocket updates
        event = DHTReadingEvent(
            temperature=reading.temperature.value,
            humidity=reading.humidity.value,
            recording_time=reading.recording_time,
        )
        self._publisher.publish(Topic.DHT_READING, event)

    @override
    def on_poll_error(self, error: Exception) -> None:
        """Handle DHT22-specific errors."""
        if isinstance(error, RuntimeError):
            # DHT library raises RuntimeError for transient sensor issues
            # (e.g., checksum failures, timing issues). Log and retry.
            logger.debug("DHT22 sensor read error: %s", error)
        else:
            super().on_poll_error(error)


def _create_sensor() -> DHTSensor:
    """Create sensor based on configuration."""
    from rpi.lib.config import get_settings

    if get_settings().mock_sensors:
        from rpi.lib.mock import MockDHTSensor

        logger.info("Using mock DHT sensor")
        return MockDHTSensor()
    from adafruit_dht import DHT22
    from board import D17

    return DHT22(D17)  # type: ignore[no-any-return]


def _create_display() -> DisplayProtocol:
    """Create display based on configuration."""
    from rpi.lib.config import get_settings

    if get_settings().mock_sensors:
        from rpi.lib.mock import MockDisplay

        return MockDisplay()
    from rpi.dht.display import Display

    return Display()


def main() -> None:
    """Main entry point for the polling service."""
    configure()
    sensor = _create_sensor()
    display = _create_display()
    service = DHTPollingService(sensor, display)
    service.run()


if __name__ == "__main__":
    main()
