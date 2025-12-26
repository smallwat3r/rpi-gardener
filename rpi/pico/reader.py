"""Read Pico moisture readings via USB serial.

Reads JSON lines from the Pico's USB serial output and persists
moisture readings to the database.
"""

import json
from datetime import UTC, datetime
from typing import Protocol, override

from rpi.lib.alerts import Namespace, get_alert_tracker, publish_alert
from rpi.lib.config import get_moisture_threshold, get_settings
from rpi.lib.db import close_db, get_db, init_db
from rpi.lib.eventbus import PicoReadingEvent, Topic, get_publisher
from rpi.lib.polling import PollingService
from rpi.logging import configure, get_logger
from rpi.pico.models import MoistureReading, ValidationError

logger = get_logger("pico.reader")


class PicoDataSource(Protocol):
    """Protocol for Pico data sources."""

    async def readline(self) -> str: ...
    def close(self) -> None: ...


class SerialDataSource:
    """Real serial port data source wrapper."""

    def __init__(self) -> None:
        import aioserial

        pico_cfg = get_settings().pico
        self._serial = aioserial.AioSerial(
            port=pico_cfg.serial_port,
            baudrate=pico_cfg.serial_baud,
            timeout=pico_cfg.serial_timeout_sec,
        )
        self._port = pico_cfg.serial_port
        logger.info("Connected to Pico on %s", self._port)

    async def readline(self) -> str:
        """Read a line from serial port."""
        data = await self._serial.readline_async()
        if not data:
            return ""
        return str(data.decode("utf-8"))

    def close(self) -> None:
        """Close the serial connection."""
        self._serial.close()
        logger.info("Serial port %s closed", self._port)


class PicoPollingService(PollingService[list[MoistureReading]]):
    """Polling service for Pico moisture sensors via USB serial."""

    def __init__(self, source: PicoDataSource) -> None:
        super().__init__(name="Pico")
        self._source = source

    @override
    async def initialize(self) -> None:
        """Initialize database, event publisher, and register alert callback."""
        await init_db()
        self._publisher = get_publisher()
        self._publisher.connect()
        tracker = get_alert_tracker()
        tracker.register_callback(Namespace.PICO, publish_alert)

    @override
    async def cleanup(self) -> None:
        """Clean up serial connection, event publisher, and database."""
        self._source.close()
        self._publisher.close()
        await close_db()

    @override
    async def poll(self) -> list[MoistureReading] | None:
        """Read and parse a JSON line from the Pico serial port."""
        line = await self._source.readline()
        if not line:
            self._logger.debug("Read timeout, no data received")
            return None

        line = line.strip()
        if not line:
            return None

        try:
            data = json.loads(line)
        except json.JSONDecodeError as e:
            self._logger.warning("Invalid JSON: %s", e)
            return None

        if not isinstance(data, dict):
            self._logger.warning(
                "Expected JSON object, got %s", type(data).__name__
            )
            return None

        recording_time = datetime.now(UTC)
        readings = []

        for key, value in data.items():
            try:
                reading = MoistureReading.from_raw(key, value, recording_time)
                readings.append(reading)
            except ValidationError as e:
                self._logger.warning("Validation failed for %s: %s", key, e)

        if readings:
            summary = ", ".join(
                f"plant-{r.plant_id}: {r.moisture}%" for r in readings
            )
            self._logger.info("Read %s", summary)
            return readings
        return None

    @override
    async def audit(self, readings: list[MoistureReading]) -> bool:
        """Check moisture levels and trigger alerts for thirsty plants."""
        tracker = get_alert_tracker()

        for reading in readings:
            threshold = get_moisture_threshold(reading.plant_id)
            is_thirsty = reading.moisture < threshold
            tracker.check(
                namespace=Namespace.PICO,
                sensor_name=reading.plant_id,
                value=reading.moisture,
                unit="%",
                threshold=threshold,
                is_violated=is_thirsty,
                recording_time=reading.recording_time,
            )

        return True

    @override
    async def persist(self, readings: list[MoistureReading]) -> None:
        """Persist moisture readings to the database and publish event."""
        async with get_db() as db:
            await db.executemany(
                "INSERT INTO pico_reading (plant_id, moisture, recording_time) "
                "VALUES (:plant_id, :moisture, :recording_time)",
                [
                    {
                        "plant_id": r.plant_id,
                        "moisture": r.moisture,
                        "recording_time": r.recording_time,
                    }
                    for r in readings
                ],
            )
        self._logger.debug("Persisted %d readings", len(readings))

        # Publish to event bus for real-time WebSocket updates
        events = [
            PicoReadingEvent(
                plant_id=r.plant_id,
                moisture=r.moisture,
                recording_time=r.recording_time,
            )
            for r in readings
        ]
        self._publisher.publish(Topic.PICO_READING, events)


def _create_data_source() -> PicoDataSource:
    """Create data source based on configuration."""
    if get_settings().mock_sensors:
        from rpi.lib.mock import MockPicoDataSource

        logger.info("Using mock Pico data source")
        return MockPicoDataSource(get_settings().polling.frequency_sec)
    return SerialDataSource()


def main() -> None:
    """Start the Pico polling service."""
    configure()
    source = _create_data_source()
    service = PicoPollingService(source)
    service.run()


if __name__ == "__main__":
    main()
