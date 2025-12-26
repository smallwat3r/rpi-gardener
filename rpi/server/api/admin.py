"""Admin settings API endpoints."""

from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator
from starlette.requests import Request
from starlette.responses import JSONResponse

from rpi.lib.config import (
    DHT22_BOUNDS,
    MeasureName,
    NotificationBackend,
    get_settings,
)
from rpi.lib.db import get_all_settings, set_settings_batch
from rpi.logging import get_logger
from rpi.server.auth import require_auth

logger = get_logger("server.api.admin")

# Extract bounds for cleaner Field definitions
TEMP_MIN, TEMP_MAX = DHT22_BOUNDS[MeasureName.TEMPERATURE]
HUM_MIN, HUM_MAX = DHT22_BOUNDS[MeasureName.HUMIDITY]


class TemperatureThreshold(BaseModel):
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


class HumidityThreshold(BaseModel):
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


class MoistureThresholds(BaseModel):
    """Moisture thresholds for default and per-plant."""

    default: int | None = Field(None, ge=0, le=100)
    plant_1: int | None = Field(None, alias="1", ge=0, le=100)
    plant_2: int | None = Field(None, alias="2", ge=0, le=100)
    plant_3: int | None = Field(None, alias="3", ge=0, le=100)

    model_config = {"populate_by_name": True}


class Thresholds(BaseModel):
    """All threshold settings."""

    temperature: TemperatureThreshold = TemperatureThreshold()
    humidity: HumidityThreshold = HumidityThreshold()
    moisture: MoistureThresholds = MoistureThresholds()


class Notifications(BaseModel):
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


class Cleanup(BaseModel):
    """Cleanup settings."""

    retentionDays: int | None = Field(None, ge=1, le=365)


class AdminSettingsRequest(BaseModel):
    """Request model for admin settings update."""

    thresholds: Thresholds = Thresholds()
    notifications: Notifications = Notifications()
    cleanup: Cleanup = Cleanup()


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
                **{
                    str(i): get_int(
                        f"threshold.moisture.{i}",
                        s.thresholds.plant_moisture_thresholds.get(
                            i, s.thresholds.min_moisture
                        ),
                    )
                    for i in (1, 2, 3)
                },
            },
        },
        "notifications": {
            "enabled": get_bool(
                "notification.enabled", s.notifications.enabled
            ),
            "backends": get_list(
                "notification.backends", [str(b) for b in s.notifications.backends]
            ),
        },
        "cleanup": {
            "retentionDays": get_int(
                "cleanup.retention_days", s.cleanup.retention_days
            ),
        },
    }


def _request_to_db_settings(data: AdminSettingsRequest) -> dict[str, str]:
    """Convert validated request data to flat DB settings."""
    result: dict[str, str] = {}

    # Thresholds
    for name, field in [
        ("temperature.min", data.thresholds.temperature.min),
        ("temperature.max", data.thresholds.temperature.max),
        ("humidity.min", data.thresholds.humidity.min),
        ("humidity.max", data.thresholds.humidity.max),
        ("moisture.default", data.thresholds.moisture.default),
        ("moisture.1", data.thresholds.moisture.plant_1),
        ("moisture.2", data.thresholds.moisture.plant_2),
        ("moisture.3", data.thresholds.moisture.plant_3),
    ]:
        if field is not None:
            result[f"threshold.{name}"] = str(field)

    # Notifications
    if data.notifications.enabled is not None:
        result["notification.enabled"] = (
            "1" if data.notifications.enabled else "0"
        )
    if data.notifications.backends is not None:
        result["notification.backends"] = ",".join(data.notifications.backends)

    # Cleanup
    if data.cleanup.retentionDays is not None:
        result["cleanup.retention_days"] = str(data.cleanup.retentionDays)

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
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    try:
        data = AdminSettingsRequest.model_validate(raw_data)
    except ValidationError as e:
        errors = [
            f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}"
            for err in e.errors()
        ]
        return JSONResponse({"errors": errors}, status_code=400)

    db_settings = _request_to_db_settings(data)
    if db_settings:
        await set_settings_batch(db_settings)
        logger.info("Admin settings updated: %s", list(db_settings.keys()))

    all_settings = await get_all_settings()
    return JSONResponse(_db_settings_to_response(all_settings))
