"""Read Pico moisture readings via USB serial.

Reads JSON lines from the Pico's USB serial output and persists
moisture readings to the database.
"""
import asyncio
import json

import aioserial

from rpi.lib.db import get_async_db, init_db
from rpi.lib.alerts import Namespace, ThresholdViolation, get_alert_tracker
from rpi.lib.config import (MOISTURE_MAX, MOISTURE_MIN, PICO_SERIAL_BAUD,
                            PICO_SERIAL_PORT, get_moisture_threshold,
                            parse_pico_plant_id)
from rpi.lib.notifications import get_notifier
from rpi.lib.utils import utcnow
from rpi.logging import configure, get_logger

logger = get_logger("pico.reader")


_pending_tasks: set[asyncio.Task] = set()


async def _send_notification_async(violation: ThresholdViolation) -> None:
    """Send notification for moisture alert asynchronously."""
    notifier = get_notifier()
    await notifier.send_async(violation)


def _schedule_notification(violation: ThresholdViolation) -> None:
    """Schedule async notification without blocking."""
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_send_notification_async(violation))
        _pending_tasks.add(task)
        task.add_done_callback(_pending_tasks.discard)
    except RuntimeError:
        # No running loop, send synchronously (shouldn't happen in normal operation)
        notifier = get_notifier()
        notifier.send(violation)


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
    if not (MOISTURE_MIN <= value <= MOISTURE_MAX):
        raise ValidationError(
            f"moisture must be between {MOISTURE_MIN} and {MOISTURE_MAX}, got {value}")
    return float(value)


async def _persist(plant_id: int, moisture: float, recording_time) -> None:
    """Persist a moisture reading to the database."""
    db = await get_async_db()
    await db.execute(
        "INSERT INTO pico_reading VALUES (?, ?, ?)",
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


async def read_serial() -> None:
    """Read lines from serial port asynchronously."""
    await init_db()
    _register_pico_alerts()
    logger.info("Opening serial port %s", PICO_SERIAL_PORT)

    ser = aioserial.AioSerial(port=PICO_SERIAL_PORT, baudrate=PICO_SERIAL_BAUD)
    logger.info("Connected to Pico on %s", PICO_SERIAL_PORT)

    try:
        while True:
            line = await ser.readline_async()
            try:
                await _handle_line(line.decode("utf-8"))
            except UnicodeDecodeError as e:
                logger.warning("Failed to decode line: %s", e)
    finally:
        ser.close()
        logger.info("Serial port %s closed", PICO_SERIAL_PORT)
        # Wait for pending notification tasks to complete
        if _pending_tasks:
            logger.info("Waiting for %d pending notification(s)", len(_pending_tasks))
            await asyncio.gather(*_pending_tasks, return_exceptions=True)


def main() -> None:
    """Start the async serial reader."""
    configure()
    asyncio.run(read_serial())


if __name__ == "__main__":
    main()
