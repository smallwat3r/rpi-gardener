"""Admin settings API endpoints."""

from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from rpi.lib.config import get_settings
from rpi.lib.db import get_all_settings, set_settings_batch
from rpi.logging import get_logger
from rpi.server.auth import require_auth

logger = get_logger("server.api.admin")

# Settings keys used in the database
SETTINGS_KEYS = {
    "threshold.temperature.min",
    "threshold.temperature.max",
    "threshold.humidity.min",
    "threshold.humidity.max",
    "threshold.moisture.default",
    "threshold.moisture.1",
    "threshold.moisture.2",
    "threshold.moisture.3",
    "notification.enabled",
    "notification.backends",
    "cleanup.retention_days",
}


def _db_settings_to_response(db_settings: dict[str, str]) -> dict[str, Any]:
    """Convert flat DB settings to structured response format."""
    s = get_settings()

    def get_int(key: str, default: int) -> int:
        val = db_settings.get(key)
        return int(val) if val is not None else default

    def get_bool(key: str, default: bool) -> bool:
        val = db_settings.get(key)
        return val == "1" if val is not None else default

    def get_list(key: str, default: list[str]) -> list[str]:
        val = db_settings.get(key)
        return (
            [x.strip() for x in val.split(",") if x.strip()]
            if val
            else default
        )

    return {
        "thresholds": {
            "temperature": {
                "min": get_int(
                    "threshold.temperature.min", s.thresholds.min_temperature
                ),
                "max": get_int(
                    "threshold.temperature.max", s.thresholds.max_temperature
                ),
            },
            "humidity": {
                "min": get_int(
                    "threshold.humidity.min", s.thresholds.min_humidity
                ),
                "max": get_int(
                    "threshold.humidity.max", s.thresholds.max_humidity
                ),
            },
            "moisture": {
                "default": get_int(
                    "threshold.moisture.default", s.thresholds.min_moisture
                ),
                "1": get_int(
                    "threshold.moisture.1",
                    s.thresholds.plant_moisture_thresholds.get(
                        1, s.thresholds.min_moisture
                    ),
                ),
                "2": get_int(
                    "threshold.moisture.2",
                    s.thresholds.plant_moisture_thresholds.get(
                        2, s.thresholds.min_moisture
                    ),
                ),
                "3": get_int(
                    "threshold.moisture.3",
                    s.thresholds.plant_moisture_thresholds.get(
                        3, s.thresholds.min_moisture
                    ),
                ),
            },
        },
        "notifications": {
            "enabled": get_bool(
                "notification.enabled", s.notifications.enabled
            ),
            "backends": get_list(
                "notification.backends", s.notifications.backends
            ),
        },
        "cleanup": {
            "retentionDays": get_int(
                "cleanup.retention_days", s.cleanup.retention_days
            ),
        },
    }


def _validate_settings(data: dict[str, Any]) -> list[str]:
    """Validate settings data. Returns list of error messages."""
    errors: list[str] = []

    thresholds = data.get("thresholds", {})
    temp = thresholds.get("temperature", {})
    humidity = thresholds.get("humidity", {})
    moisture = thresholds.get("moisture", {})

    # Temperature validation
    temp_min = temp.get("min")
    temp_max = temp.get("max")
    if temp_min is not None and temp_max is not None:
        if not isinstance(temp_min, int) or not isinstance(temp_max, int):
            errors.append("Temperature thresholds must be integers")
        elif temp_min >= temp_max:
            errors.append("Temperature min must be less than max")
        elif temp_min < -40 or temp_max > 80:
            errors.append("Temperature must be within [-40, 80]")

    # Humidity validation
    hum_min = humidity.get("min")
    hum_max = humidity.get("max")
    if hum_min is not None and hum_max is not None:
        if not isinstance(hum_min, int) or not isinstance(hum_max, int):
            errors.append("Humidity thresholds must be integers")
        elif hum_min >= hum_max:
            errors.append("Humidity min must be less than max")
        elif hum_min < 0 or hum_max > 100:
            errors.append("Humidity must be within [0, 100]")

    # Moisture validation
    for key in ["default", "1", "2", "3"]:
        val = moisture.get(key)
        if val is not None:
            if not isinstance(val, int):
                errors.append(f"Moisture threshold '{key}' must be an integer")
            elif val < 0 or val > 100:
                errors.append(
                    f"Moisture threshold '{key}' must be within [0, 100]"
                )

    # Notifications validation
    notifications = data.get("notifications", {})
    backends = notifications.get("backends")
    if backends is not None:
        if not isinstance(backends, list):
            errors.append("Notification backends must be a list")
        else:
            valid_backends = {"gmail", "slack"}
            for b in backends:
                if b not in valid_backends:
                    errors.append(f"Invalid notification backend: {b}")

    # Cleanup validation
    cleanup = data.get("cleanup", {})
    retention = cleanup.get("retentionDays")
    if retention is not None:
        if not isinstance(retention, int):
            errors.append("Retention days must be an integer")
        elif retention < 1 or retention > 365:
            errors.append("Retention days must be between 1 and 365")

    return errors


def _request_to_db_settings(data: dict[str, Any]) -> dict[str, str]:
    """Convert structured request data to flat DB settings."""
    result: dict[str, str] = {}

    thresholds = data.get("thresholds", {})
    temp = thresholds.get("temperature", {})
    humidity = thresholds.get("humidity", {})
    moisture = thresholds.get("moisture", {})

    if "min" in temp:
        result["threshold.temperature.min"] = str(temp["min"])
    if "max" in temp:
        result["threshold.temperature.max"] = str(temp["max"])
    if "min" in humidity:
        result["threshold.humidity.min"] = str(humidity["min"])
    if "max" in humidity:
        result["threshold.humidity.max"] = str(humidity["max"])
    if "default" in moisture:
        result["threshold.moisture.default"] = str(moisture["default"])
    for key in ["1", "2", "3"]:
        if key in moisture:
            result[f"threshold.moisture.{key}"] = str(moisture[key])

    notifications = data.get("notifications", {})
    if "enabled" in notifications:
        result["notification.enabled"] = (
            "1" if notifications["enabled"] else "0"
        )
    if "backends" in notifications:
        result["notification.backends"] = ",".join(notifications["backends"])

    cleanup = data.get("cleanup", {})
    if "retentionDays" in cleanup:
        result["cleanup.retention_days"] = str(cleanup["retentionDays"])

    return result


@require_auth
async def get_admin_settings(request: Request) -> JSONResponse:
    """Get all admin-configurable settings.

    GET /api/admin/settings
    """
    db_settings = await get_all_settings()
    response_data = _db_settings_to_response(db_settings)
    return JSONResponse(response_data)


@require_auth
async def update_admin_settings(request: Request) -> JSONResponse:
    """Update admin settings.

    PUT /api/admin/settings
    Body: {
        "thresholds": {
            "temperature": {"min": 18, "max": 25},
            "humidity": {"min": 40, "max": 65},
            "moisture": {"default": 30, "1": 55, "2": 30, "3": 35}
        },
        "notifications": {
            "enabled": true,
            "backends": ["gmail", "slack"]
        },
        "cleanup": {
            "retentionDays": 3
        }
    }
    """
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    errors = _validate_settings(data)
    if errors:
        return JSONResponse({"errors": errors}, status_code=400)

    db_settings = _request_to_db_settings(data)
    if db_settings:
        await set_settings_batch(db_settings)
        logger.info("Admin settings updated: %s", list(db_settings.keys()))

    # Return current settings after update
    all_settings = await get_all_settings()
    response_data = _db_settings_to_response(all_settings)
    return JSONResponse(response_data)
