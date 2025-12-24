"""Read Pico moisture readings via USB serial.

Reads JSON lines from the Pico's USB serial output and persists
moisture readings to the database.
"""
import asyncio
import json

import aioserial

from sqlitey import Sql

from rpi import logging
from rpi.lib.config import (
    MOISTURE_MAX,
    MOISTURE_MIN,
    PLANT_ID_MAX_LENGTH,
    PLANT_ID_PATTERN,
    db_with_config,
    get_moisture_threshold,
)
from rpi.lib.notifications import Event, get_notifier
from rpi.lib.utils import utcnow

logger = logging.getLogger("pico-serial")

SERIAL_PORT = "/dev/ttyACM0"
SERIAL_BAUD = 115200

# Track alert state per plant to avoid repeated notifications
_alert_state: dict[str, bool] = {}


class ValidationError(Exception):
    """Raised when input validation fails."""


def _validate_plant_id(plant_id: str) -> str:
    """Validate plant_id is a safe, non-empty string within length limits."""
    if not isinstance(plant_id, str):
        raise ValidationError(f"plant_id must be a string, got {type(plant_id).__name__}")
    if not plant_id or len(plant_id) > PLANT_ID_MAX_LENGTH:
        raise ValidationError(f"plant_id must be 1-{PLANT_ID_MAX_LENGTH} characters")
    if not PLANT_ID_PATTERN.match(plant_id):
        raise ValidationError("plant_id must contain only alphanumeric, hyphens, or underscores")
    return plant_id


def _validate_moisture(value: float) -> float:
    """Validate moisture value is a number within valid bounds."""
    if not isinstance(value, (int, float)):
        raise ValidationError(f"moisture must be a number, got {type(value).__name__}")
    if not (MOISTURE_MIN <= value <= MOISTURE_MAX):
        raise ValidationError(
            f"moisture must be between {MOISTURE_MIN} and {MOISTURE_MAX}, got {value}")
    return float(value)


def _persist(plant_id: str, moisture: float, recording_time) -> None:
    """Persist a moisture reading to the database."""
    with db_with_config() as db:
        db.commit(Sql.raw("INSERT INTO pico_reading VALUES (?, ?, ?)"),
                  (plant_id, moisture, recording_time))


def _audit_moisture(plant_id: str, moisture: float, recording_time) -> None:
    """Check moisture level and send notification if plant is thirsty."""
    threshold = get_moisture_threshold(plant_id)
    was_in_alert = _alert_state.get(plant_id, False)
    is_thirsty = moisture < threshold

    if is_thirsty and not was_in_alert:
        logger.info("Plant %s is thirsty (moisture: %.1f%%, threshold: %d%%)",
                    plant_id, moisture, threshold)
        notifier = get_notifier()
        notifier.send(Event(
            sensor_name=plant_id,
            value=moisture,
            unit="%",
            threshold=threshold,
            recording_time=recording_time,
        ))

    _alert_state[plant_id] = is_thirsty


def _process_readings(data: dict) -> int:
    """Validate and persist readings from parsed JSON data."""
    current_time = utcnow()
    persisted = 0

    for key, value in data.items():
        try:
            plant_id = _validate_plant_id(key)
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
    logger.info("Opening serial port %s", SERIAL_PORT)

    ser = aioserial.AioSerial(port=SERIAL_PORT, baudrate=SERIAL_BAUD)
    logger.info("Connected to Pico on %s", SERIAL_PORT)

    while True:
        line = await ser.readline_async()
        try:
            _handle_line(line.decode("utf-8"))
        except UnicodeDecodeError as e:
            logger.warning("Failed to decode line: %s", e)


def main() -> None:
    """Start the async serial reader."""
    asyncio.run(read_serial())


if __name__ == "__main__":
    main()
