from datetime import datetime
from typing import Any

from flask import Blueprint, Response, jsonify, request
from sqlitey import Sql

from rpi import logging
from rpi.lib.config import (
    MOISTURE_MAX,
    MOISTURE_MIN,
    PLANT_ID_MAX_LENGTH,
    PLANT_ID_PATTERN,
    db_with_config,
)
from rpi.lib.reading import Measure, PicoReading, Unit

logger = logging.getLogger("pico-bp")
pico = Blueprint("pico", __name__)


class _ValidationError(Exception):
    """Raised when input validation fails."""


def _validate_plant_id(plant_id: Any) -> str:
    """Validate plant_id is a safe, non-empty string within length limits.

    Only alphanumeric characters, hyphens, and underscores are allowed
    to prevent XSS when rendered in HTML templates.
    """
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


def _persist(reading: PicoReading) -> None:
    with db_with_config() as db:
        db.commit(Sql.raw("INSERT INTO pico_reading VALUES (?, ?, ?)"),
                  (reading.plant_id, reading.moisture.value,
                   reading.recording_time))


@pico.post("/pico")
def receive() -> tuple[Response, int]:
    """Receive and persist moisture readings from Pico device."""
    current_time = datetime.utcnow()
    data = request.get_json()

    if data is None:
        logger.warning("Received empty or invalid JSON payload")
        return jsonify({"error": "Invalid JSON payload"}), 400

    if not isinstance(data, dict):
        logger.warning("Received non-dict JSON: %s", type(data).__name__)
        return jsonify({"error": "Expected JSON object"}), 400

    logger.info("Received Pico data: %s", data)
    persisted = 0

    for key, value in data.items():
        try:
            plant_id = _validate_plant_id(key)
            moisture = _validate_moisture(value)
            _persist(PicoReading(plant_id, Measure(moisture, Unit.PERCENT), current_time))
            persisted += 1
        except _ValidationError as e:
            logger.warning("Validation failed for %s: %s", key, e)
            continue
        except Exception as e:
            logger.error("Failed to persist reading for %s: %s", key, e)
            continue

    if persisted == 0 and data:
        return jsonify({"error": "No valid readings in payload"}), 400

    return jsonify({"persisted": persisted}), 201
