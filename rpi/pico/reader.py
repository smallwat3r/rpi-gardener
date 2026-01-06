"""Read Pico moisture readings via USB serial.

Reads JSON lines from the Pico's USB serial output and persists
moisture readings to the database.
"""

import asyncio
import json
from datetime import UTC, datetime
from typing import Protocol, override

from rpi.lib.alerts import AlertTracker, Namespace, create_alert_publisher
from rpi.lib.config import (
    ThresholdType,
    Unit,
    get_effective_thresholds,
    get_settings,
)
from rpi.lib.db import close_db, get_db, init_db
from rpi.lib.eventbus import EventPublisher, PicoReadingEvent
from rpi.lib.polling import PollingService
from rpi.logging import configure, get_logger
from rpi.pico.models import MoistureReading, ValidationError

logger = get_logger("pico.reader")

# Timeout for serial read operations (in addition to serial port timeout)
# Prevents indefinite blocking if serial port becomes unresponsive
_READ_TIMEOUT_SEC = 60.0


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
    """Polling service for Pico moisture sensors via USB serial.

    Includes spike rejection to filter out erroneous sensor readings that
    jump too far from previous values (e.g., broken sensors returning 100%).
    """

    def __init__(
        self,
        source: PicoDataSource,
        publisher: EventPublisher,
        alert_tracker: AlertTracker,
    ) -> None:
        super().__init__(name="Pico")
        self._source = source
        self._publisher = publisher
        self._alert_tracker = alert_tracker
        self._last_readings: dict[int, float] = {}
        self._spike_threshold = get_settings().pico.spike_threshold

    def _is_spike(self, plant_id: int, moisture: float) -> bool:
        """Detect sudden jumps to 100% that indicate sensor errors.

        Capacitive moisture sensors can malfunction and return 100% when
        there's a connection issue or the sensor is damaged. We only reject
        spikes toward 100% to avoid blocking legitimate recovery after
        watering (which can cause large sudden increases).

        Returns True if the reading jumps to 100% by more than the configured
        spike threshold. First readings are never spikes.
        """
        if plant_id not in self._last_readings:
            return False
        if moisture < 100.0:
            return False
        delta = moisture - self._last_readings[plant_id]
        return delta > self._spike_threshold

    def _update_last_reading(self, plant_id: int, moisture: float) -> None:
        """Update the last known reading for a plant."""
        self._last_readings[plant_id] = moisture

    @override
    async def initialize(self) -> None:
        """Initialize database and register alert callback."""
        await init_db()
        self._publisher.connect()
        self._alert_tracker.register_callback(
            Namespace.PICO, create_alert_publisher(self._publisher)
        )

    @override
    async def cleanup(self) -> None:
        """Clean up serial connection, event publisher, and database."""
        self._source.close()
        self._publisher.close()
        await close_db()

    @override
    async def poll(self) -> list[MoistureReading] | None:
        """Read and parse a JSON line from the Pico serial port."""
        try:
            line = await asyncio.wait_for(
                self._source.readline(),
                timeout=_READ_TIMEOUT_SEC,
            )
        except TimeoutError:
            self._logger.warning(
                "Serial read timed out after %ds", _READ_TIMEOUT_SEC
            )
            return None
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
            except ValidationError as e:
                self._logger.warning("Validation failed for %s: %s", key, e)
                continue

            if self._is_spike(reading.plant_id, reading.moisture):
                self._logger.warning(
                    "Spike rejected for plant-%d: %.1f%% (last: %.1f%%, threshold: %.1f%%)",
                    reading.plant_id,
                    reading.moisture,
                    self._last_readings[reading.plant_id],
                    self._spike_threshold,
                )
                continue

            self._update_last_reading(reading.plant_id, reading.moisture)
            readings.append(reading)

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
        thresholds = await get_effective_thresholds()

        for reading in readings:
            self._alert_tracker.check(
                namespace=Namespace.PICO,
                sensor_name=reading.plant_id,
                value=reading.moisture,
                unit=Unit.PERCENT,
                threshold=thresholds.get_moisture_threshold(reading.plant_id),
                threshold_type=ThresholdType.MIN,
                hysteresis=thresholds.moisture_hysteresis,
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
        self._publisher.publish(events)


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
    publisher = EventPublisher()
    alert_tracker = AlertTracker()
    service = PicoPollingService(source, publisher, alert_tracker)
    service.run()


if __name__ == "__main__":
    main()
