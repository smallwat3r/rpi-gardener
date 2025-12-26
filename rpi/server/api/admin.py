"""Admin settings API endpoints."""

from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from rpi.lib.config import NotificationBackend, get_settings
from rpi.lib.db import get_all_settings, set_settings_batch
from rpi.logging import get_logger
from rpi.server.auth import require_auth
from rpi.server.validators import (
    validate_int_range,
    validate_list_items,
    validate_min_max_pair,
)

logger = get_logger("server.api.admin")


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
    thresholds = data.get("thresholds", {})
    temp = thresholds.get("temperature", {})
    humidity = thresholds.get("humidity", {})
    moisture = thresholds.get("moisture", {})
    notifications = data.get("notifications", {})
    cleanup = data.get("cleanup", {})

    errors: list[str] = [
        *validate_min_max_pair(
            temp.get("min"), temp.get("max"), "Temperature", -40, 80
        ),
        *validate_min_max_pair(
            humidity.get("min"), humidity.get("max"), "Humidity", 0, 100
        ),
        *[
            e
            for key in ("default", "1", "2", "3")
            if (e := validate_int_range(moisture.get(key), f"Moisture '{key}'", 0, 100))
        ],
        *validate_list_items(
            notifications.get("backends"), "notification backend", set(NotificationBackend)
        ),
        *[
            e
            for e in [validate_int_range(cleanup.get("retentionDays"), "Retention days", 1, 365)]
            if e
        ],
    ]
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
    for key in ("1", "2", "3"):
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
