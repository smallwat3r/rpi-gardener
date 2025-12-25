"""Read Pico moisture readings via USB serial.

Reads JSON lines from the Pico's USB serial output and persists
moisture readings to the database.
"""
import asyncio
import json
from typing import Protocol

from rpi.lib.alerts import AlertEvent, Namespace, get_alert_tracker
from rpi.lib.config import (get_moisture_threshold, get_settings,
                            parse_pico_plant_id)
from rpi.lib.db import close_db, get_db, init_db
from rpi.lib.notifications import get_notifier
from rpi.lib.utils import utcnow
from rpi.logging import configure, get_logger

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
        return data.decode("utf-8")

    def close(self) -> None:
        """Close the serial connection."""
        self._serial.close()
        logger.info("Serial port %s closed", self._port)


_pending_tasks: set[asyncio.Task] = set()


async def _send_notification(event: AlertEvent) -> None:
    """Send notification for alert event."""
    notifier = get_notifier()
    await notifier.send(event)


def _schedule_notification(event: AlertEvent) -> None:
    """Schedule async notification without blocking."""
    loop = asyncio.get_running_loop()
    task = loop.create_task(_send_notification(event))
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)


def _register_pico_alerts() -> None:
    """Register the Pico namespace callback with the global alert tracker."""
    tracker = get_alert_tracker()
    tracker.register_callback(Namespace.PICO, _schedule_notification)


class ValidationError(Exception):
    """Raised when input validation fails."""


def _parse_plant_id(raw_id: str) -> int:
    """Parse and validate plant_id from Pico's 'plant-N' format."""
    if not isinstance(raw_id, str):
        raise ValidationError(f"plant_id must be a string, got {type(raw_id).__name__}")
    plant_id = parse_pico_plant_id(raw_id)
    if plant_id is None:
        raise ValidationError(f"plant_id must be in 'plant-N' format, got '{raw_id}'")
    return plant_id


def _validate_moisture(value: float) -> float:
    """Validate moisture value is a number within valid bounds."""
    if not isinstance(value, (int, float)):
        raise ValidationError(f"moisture must be a number, got {type(value).__name__}")
    pico_cfg = get_settings().pico
    min_val = pico_cfg.moisture_min
    max_val = pico_cfg.moisture_max
    if not (min_val <= value <= max_val):
        raise ValidationError(
            f"moisture must be between {min_val} and {max_val}, got {value}")
    return float(value)


async def _persist(plant_id: int, moisture: float, recording_time) -> None:
    """Persist a moisture reading to the database."""
    async with get_db() as db:
        await db.execute(
            "INSERT INTO pico_reading (plant_id, moisture, recording_time) VALUES (?, ?, ?)",
            (plant_id, moisture, recording_time)
        )


def _audit_moisture(plant_id: int, moisture: float, recording_time) -> None:
    """Check moisture level and trigger alert if plant is thirsty."""
    threshold = get_moisture_threshold(plant_id)
    is_thirsty = moisture < threshold
    tracker = get_alert_tracker()

    tracker.check(
        namespace=Namespace.PICO,
        sensor_name=plant_id,
        value=moisture,
        unit="%",
        threshold=threshold,
        is_violated=is_thirsty,
        recording_time=recording_time,
    )


async def _process_readings(data: dict) -> int:
    """Validate and persist readings from parsed JSON data."""
    current_time = utcnow()
    persisted = 0

    for key, value in data.items():
        try:
            plant_id = _parse_plant_id(key)
            moisture = _validate_moisture(value)
            await _persist(plant_id, moisture, current_time)
            _audit_moisture(plant_id, moisture, current_time)
            persisted += 1
        except ValidationError as e:
            logger.warning("Validation failed for %s: %s", key, e)
        except Exception as e:
            logger.error("Failed to persist reading for %s: %s", key, e)

    return persisted


async def _handle_line(line: str) -> None:
    """Process a single line of JSON data."""
    line = line.strip()
    if not line:
        return

    try:
        data = json.loads(line)
        if not isinstance(data, dict):
            logger.warning("Expected JSON object, got %s", type(data).__name__)
            return

        persisted = await _process_readings(data)
        logger.debug("Persisted %d readings", persisted)

    except json.JSONDecodeError as e:
        logger.warning("Invalid JSON: %s", e)


async def read_data(source: PicoDataSource) -> None:
    """Read lines from data source asynchronously."""
    await init_db()
    _register_pico_alerts()

    try:
        while True:
            line = await source.readline()
            if not line:
                logger.debug("Read timeout, no data received")
                continue
            await _handle_line(line)
    finally:
        source.close()
        # Wait for pending notification tasks to complete (with timeout)
        if _pending_tasks:
            logger.info("Waiting for %d pending notification(s)", len(_pending_tasks))
            try:
                await asyncio.wait_for(
                    asyncio.gather(*_pending_tasks, return_exceptions=True),
                    timeout=get_settings().notifications.timeout_sec,
                )
            except TimeoutError:
                logger.warning("Timed out waiting for pending notifications")
        await close_db()


def _create_data_source() -> PicoDataSource:
    """Create data source based on configuration."""
    if get_settings().mock_sensors:
        from rpi.lib.mock import MockPicoDataSource
        logger.info("Using mock Pico data source")
        return MockPicoDataSource(get_settings().polling.frequency_sec)
    return SerialDataSource()


def main() -> None:
    """Start the async data reader."""
    configure()
    source = _create_data_source()
    asyncio.run(read_data(source))


if __name__ == "__main__":
    main()
