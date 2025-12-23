from datetime import datetime
from typing import Any

from sqlitey import Sql
from starlette.requests import Request
from starlette.responses import JSONResponse

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

logger = logging.getLogger("pico-api")

# Track alert state per plant to avoid repeated notifications
_alert_state: dict[str, bool] = {}


class _ValidationError(Exception):
    """Raised when input validation fails."""


def _validate_plant_id(plant_id: Any) -> str:
    """Validate plant_id is a safe, non-empty string within length limits."""
    if not isinstance(plant_id, str):
        raise _ValidationError(f"plant_id must be a string, got {type(plant_id).__name__}")
    if not plant_id or len(plant_id) > PLANT_ID_MAX_LENGTH:
        raise _ValidationError(f"plant_id must be 1-{PLANT_ID_MAX_LENGTH} characters")
    if not PLANT_ID_PATTERN.match(plant_id):
        raise _ValidationError("plant_id must contain only alphanumeric, hyphens, or underscores")
    return plant_id


def _validate_moisture(value: Any) -> float:
    """Validate moisture value is a number within valid bounds."""
    if not isinstance(value, (int, float)):
        raise _ValidationError(f"moisture must be a number, got {type(value).__name__}")
    if not (MOISTURE_MIN <= value <= MOISTURE_MAX):
        raise _ValidationError(
            f"moisture must be between {MOISTURE_MIN} and {MOISTURE_MAX}, got {value}")
    return float(value)


def _persist(plant_id: str, moisture: float, recording_time: datetime) -> None:
    with db_with_config() as db:
        db.commit(Sql.raw("INSERT INTO pico_reading VALUES (?, ?, ?)"),
                  (plant_id, moisture, recording_time))


def _audit_moisture(plant_id: str, moisture: float, recording_time: datetime) -> None:
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


async def receive_pico_data(request: Request) -> JSONResponse:
    """Receive and persist moisture readings from Pico device."""
    current_time = utcnow()

    try:
        data = await request.json()
    except Exception:
        logger.warning("Received empty or invalid JSON payload")
        return JSONResponse({"error": "Invalid JSON payload"}, status_code=400)

    if not isinstance(data, dict):
        logger.warning("Received non-dict JSON: %s", type(data).__name__)
        return JSONResponse({"error": "Expected JSON object"}, status_code=400)

    logger.info("Received Pico data: %s", data)
    persisted = 0

    for key, value in data.items():
        try:
            plant_id = _validate_plant_id(key)
            moisture = _validate_moisture(value)
            _persist(plant_id, moisture, current_time)
            _audit_moisture(plant_id, moisture, current_time)
            persisted += 1
        except _ValidationError as e:
            logger.warning("Validation failed for %s: %s", key, e)
            continue
        except Exception as e:
            logger.error("Failed to persist reading for %s: %s", key, e)
            continue

    if persisted == 0 and data:
        return JSONResponse({"error": "No valid readings in payload"}, status_code=400)

    return JSONResponse({"persisted": persisted}, status_code=201)
