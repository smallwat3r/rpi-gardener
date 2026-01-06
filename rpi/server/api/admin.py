"""Admin settings API endpoints."""

import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator
from starlette.requests import Request
from starlette.responses import JSONResponse

from rpi.lib.config import (
    DHT22_BOUNDS,
    MeasureName,
    NotificationBackend,
    SettingsKey,
    get_settings,
)
from rpi.lib.db import get_all_settings, set_settings_batch
from rpi.logging import get_logger
from rpi.server.auth import require_auth

logger = get_logger("server.api.admin")

# Extract bounds for cleaner Field definitions
TEMP_MIN, TEMP_MAX = DHT22_BOUNDS[MeasureName.TEMPERATURE]
HUM_MIN, HUM_MAX = DHT22_BOUNDS[MeasureName.HUMIDITY]


class _TemperatureThreshold(BaseModel):
    """Temperature threshold with validation."""

    min: int | None = Field(None, ge=TEMP_MIN, le=TEMP_MAX)
    max: int | None = Field(None, ge=TEMP_MIN, le=TEMP_MAX)

    @field_validator("max")
    @classmethod
    def max_gt_min(cls, v: int | None, info: Any) -> int | None:
        if v is not None and info.data.get("min") is not None:
            if v <= info.data["min"]:
                raise ValueError("max must be greater than min")
        return v


class _HumidityThreshold(BaseModel):
    """Humidity threshold with validation."""

    min: int | None = Field(None, ge=HUM_MIN, le=HUM_MAX)
    max: int | None = Field(None, ge=HUM_MIN, le=HUM_MAX)

    @field_validator("max")
    @classmethod
    def max_gt_min(cls, v: int | None, info: Any) -> int | None:
        if v is not None and info.data.get("min") is not None:
            if v <= info.data["min"]:
                raise ValueError("max must be greater than min")
        return v


class _MoistureThresholds(BaseModel):
    """Moisture thresholds for default and per-plant."""

    default: int | None = Field(None, ge=0, le=100)
    plant_1: int | None = Field(None, alias="1", ge=0, le=100)
    plant_2: int | None = Field(None, alias="2", ge=0, le=100)
    plant_3: int | None = Field(None, alias="3", ge=0, le=100)

    model_config = {"populate_by_name": True}


class _Thresholds(BaseModel):
    """All threshold settings."""

    temperature: _TemperatureThreshold = _TemperatureThreshold()
    humidity: _HumidityThreshold = _HumidityThreshold()
    moisture: _MoistureThresholds = _MoistureThresholds()


class _Notifications(BaseModel):
    """Notification settings."""

    enabled: bool | None = None
    backends: list[str] | None = None

    @field_validator("backends")
    @classmethod
    def validate_backends(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        valid = {b.value for b in NotificationBackend}
        invalid = [b for b in v if b not in valid]
        if invalid:
            raise ValueError(f"Invalid backends: {invalid}")
        return v


class _Cleanup(BaseModel):
    """Cleanup settings."""

    retentionDays: int | None = Field(None, ge=1, le=365)


class _AdminSettingsRequest(BaseModel):
    """Request model for admin settings update."""

    thresholds: _Thresholds = _Thresholds()
    notifications: _Notifications = _Notifications()
    cleanup: _Cleanup = _Cleanup()


class _SettingsReader:
    """Helper to read typed values from flat DB settings with defaults."""

    def __init__(self, db_settings: dict[SettingsKey, str]):
        self._db = db_settings

    def get_int(self, key: SettingsKey, default: int) -> int:
        val = self._db.get(key)
        return int(val) if val is not None else default

    def get_bool(self, key: SettingsKey, default: bool) -> bool:
        val = self._db.get(key)
        return val == "1" if val is not None else default

    def get_list(self, key: SettingsKey, default: list[str]) -> list[str]:
        val = self._db.get(key)
        return (
            [x.strip() for x in val.split(",") if x.strip()]
            if val
            else default
        )


def _db_settings_to_response(
    db_settings: dict[SettingsKey, str],
) -> dict[str, Any]:
    """Convert flat DB settings to structured response format."""
    s = get_settings()
    r = _SettingsReader(db_settings)
    plant_thresholds = s.thresholds.plant_moisture_thresholds
    default_moisture = s.thresholds.min_moisture

    return {
        "thresholds": {
            "temperature": {
                "min": r.get_int(
                    SettingsKey.TEMP_MIN, s.thresholds.min_temperature
                ),
                "max": r.get_int(
                    SettingsKey.TEMP_MAX, s.thresholds.max_temperature
                ),
            },
            "humidity": {
                "min": r.get_int(
                    SettingsKey.HUMIDITY_MIN, s.thresholds.min_humidity
                ),
                "max": r.get_int(
                    SettingsKey.HUMIDITY_MAX, s.thresholds.max_humidity
                ),
            },
            "moisture": {
                "default": r.get_int(
                    SettingsKey.MOISTURE_DEFAULT, default_moisture
                ),
                "1": r.get_int(
                    SettingsKey.MOISTURE_1,
                    plant_thresholds.get(1, default_moisture),
                ),
                "2": r.get_int(
                    SettingsKey.MOISTURE_2,
                    plant_thresholds.get(2, default_moisture),
                ),
                "3": r.get_int(
                    SettingsKey.MOISTURE_3,
                    plant_thresholds.get(3, default_moisture),
                ),
            },
        },
        "notifications": {
            "enabled": r.get_bool(
                SettingsKey.NOTIFICATION_ENABLED, s.notifications.enabled
            ),
            "backends": r.get_list(
                SettingsKey.NOTIFICATION_BACKENDS,
                [str(b) for b in s.notifications.backends],
            ),
        },
        "cleanup": {
            "retentionDays": r.get_int(
                SettingsKey.RETENTION_DAYS, s.cleanup.retention_days
            ),
        },
    }


def _request_to_db_settings(
    data: _AdminSettingsRequest,
) -> dict[SettingsKey, str]:
    """Convert validated request data to flat DB settings."""
    result: dict[SettingsKey, str] = {}

    # Thresholds
    threshold_fields: list[tuple[SettingsKey, int | None]] = [
        (SettingsKey.TEMP_MIN, data.thresholds.temperature.min),
        (SettingsKey.TEMP_MAX, data.thresholds.temperature.max),
        (SettingsKey.HUMIDITY_MIN, data.thresholds.humidity.min),
        (SettingsKey.HUMIDITY_MAX, data.thresholds.humidity.max),
        (SettingsKey.MOISTURE_DEFAULT, data.thresholds.moisture.default),
        (SettingsKey.MOISTURE_1, data.thresholds.moisture.plant_1),
        (SettingsKey.MOISTURE_2, data.thresholds.moisture.plant_2),
        (SettingsKey.MOISTURE_3, data.thresholds.moisture.plant_3),
    ]
    for key, field in threshold_fields:
        if field is not None:
            result[key] = str(field)

    # Notifications
    if data.notifications.enabled is not None:
        result[SettingsKey.NOTIFICATION_ENABLED] = (
            "1" if data.notifications.enabled else "0"
        )
    if data.notifications.backends is not None:
        result[SettingsKey.NOTIFICATION_BACKENDS] = ",".join(
            data.notifications.backends
        )

    # Cleanup
    if data.cleanup.retentionDays is not None:
        result[SettingsKey.RETENTION_DAYS] = str(data.cleanup.retentionDays)

    return result


@require_auth
async def get_admin_settings(request: Request) -> JSONResponse:
    """Get all admin-configurable settings."""
    db_settings = await get_all_settings()
    return JSONResponse(_db_settings_to_response(db_settings))


@require_auth
async def update_admin_settings(request: Request) -> JSONResponse:
    """Update admin settings."""
    try:
        raw_data = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    try:
        data = _AdminSettingsRequest.model_validate(raw_data)
    except ValidationError as e:
        errors = [
            f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}"
            for err in e.errors()
        ]
        return JSONResponse({"errors": errors}, status_code=400)

    db_settings = _request_to_db_settings(data)
    if db_settings:
        all_settings = await set_settings_batch(db_settings)
        logger.info("Admin settings updated: %s", list(db_settings.keys()))
    else:
        all_settings = await get_all_settings()

    return JSONResponse(_db_settings_to_response(all_settings))
