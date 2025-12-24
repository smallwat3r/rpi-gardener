"""Read Pico moisture readings via USB serial.

Reads JSON lines from the Pico's USB serial output and persists
moisture readings to the database.
"""
import asyncio
import json

import aioserial

from sqlitey import Sql

from rpi.lib.alerts import AlertTracker
from rpi.logging import configure, get_logger
from rpi.lib.config import (
    MOISTURE_MAX,
    MOISTURE_MIN,
    PICO_SERIAL_BAUD,
    PICO_SERIAL_PORT,
    db_with_config,
    get_moisture_threshold,
    parse_pico_plant_id,
)
from rpi.lib.notifications import Event, get_notifier
from rpi.lib.utils import utcnow

logger = get_logger("pico.reader")


_pending_tasks: set[asyncio.Task] = set()


async def _send_notification_async(event: Event) -> None:
    """Send notification for moisture alert asynchronously."""
    notifier = get_notifier()
    await notifier.send_async(event)


def _schedule_notification(event: Event) -> None:
    """Schedule async notification without blocking."""
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_send_notification_async(event))
        _pending_tasks.add(task)
        task.add_done_callback(_pending_tasks.discard)
    except RuntimeError:
        # No running loop, send synchronously (shouldn't happen in normal operation)
        notifier = get_notifier()
        notifier.send(event)


_alert_tracker = AlertTracker(on_alert=_schedule_notification)


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


def _persist(plant_id: int, moisture: float, recording_time) -> None:
    """Persist a moisture reading to the database."""
    with db_with_config() as db:
        db.commit(Sql.raw("INSERT INTO pico_reading VALUES (?, ?, ?)"),
                  (plant_id, moisture, recording_time))


def _audit_moisture(plant_id: int, moisture: float, recording_time) -> None:
    """Check moisture level and send notification if plant is thirsty."""
    threshold = get_moisture_threshold(plant_id)
    is_thirsty = moisture < threshold

    _alert_tracker.check(
        sensor_name=plant_id,
        value=moisture,
        unit="%",
        threshold=threshold,
        is_violated=is_thirsty,
        recording_time=recording_time,
    )


def _process_readings(data: dict) -> int:
    """Validate and persist readings from parsed JSON data."""
    current_time = utcnow()
    persisted = 0

    for key, value in data.items():
        try:
            plant_id = _parse_plant_id(key)
            moisture = _validate_moisture(value)
            _persist(plant_id, moisture, current_time)
            _audit_moisture(plant_id, moisture, current_time)
            persisted += 1
        except ValidationError as e:
            logger.warning("Validation failed for %s: %s", key, e)
        except Exception as e:
            logger.error("Failed to persist reading for %s: %s", key, e)

    return persisted


def _handle_line(line: str) -> None:
    """Process a single line of JSON data."""
    line = line.strip()
    if not line:
        return

    try:
        data = json.loads(line)
        if not isinstance(data, dict):
            logger.warning("Expected JSON object, got %s", type(data).__name__)
            return

        persisted = _process_readings(data)
        logger.debug("Persisted %d readings", persisted)

    except json.JSONDecodeError as e:
        logger.warning("Invalid JSON: %s", e)


async def read_serial() -> None:
    """Read lines from serial port asynchronously."""
    logger.info("Opening serial port %s", PICO_SERIAL_PORT)

    ser = aioserial.AioSerial(port=PICO_SERIAL_PORT, baudrate=PICO_SERIAL_BAUD)
    logger.info("Connected to Pico on %s", PICO_SERIAL_PORT)

    try:
        while True:
            line = await ser.readline_async()
            try:
                _handle_line(line.decode("utf-8"))
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
