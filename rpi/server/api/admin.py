"""Admin settings API endpoints."""

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator
from starlette.requests import Request
from starlette.responses import JSONResponse

from rpi.lib.config import NotificationBackend, get_settings
from rpi.lib.db import get_all_settings, set_settings_batch
from rpi.logging import get_logger
from rpi.server.auth import require_auth

logger = get_logger("server.api.admin")


class MinMax(BaseModel):
    """Min/max threshold pair."""

    min: int | None = None
    max: int | None = None


class TemperatureThreshold(MinMax):
    """Temperature threshold with validation."""

    @model_validator(mode="after")
    def validate_range(self) -> TemperatureThreshold:
        if self.min is not None and self.max is not None:
            if self.min >= self.max:
                raise ValueError("Temperature min must be less than max")
            if self.min < -40 or self.max > 80:
                raise ValueError("Temperature must be within [-40, 80]")
        return self


class HumidityThreshold(MinMax):
    """Humidity threshold with validation."""

    @model_validator(mode="after")
    def validate_range(self) -> HumidityThreshold:
        if self.min is not None and self.max is not None:
            if self.min >= self.max:
                raise ValueError("Humidity min must be less than max")
            if self.min < 0 or self.max > 100:
                raise ValueError("Humidity must be within [0, 100]")
        return self


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
        valid = set(NotificationBackend)
        for backend in v:
            if backend not in valid:
                raise ValueError(f"Invalid notification backend: {backend}")
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


def _request_to_db_settings(data: AdminSettingsRequest) -> dict[str, str]:
    """Convert validated request data to flat DB settings."""
    result: dict[str, str] = {}

    temp = data.thresholds.temperature
    if temp.min is not None:
        result["threshold.temperature.min"] = str(temp.min)
    if temp.max is not None:
        result["threshold.temperature.max"] = str(temp.max)

    humidity = data.thresholds.humidity
    if humidity.min is not None:
        result["threshold.humidity.min"] = str(humidity.min)
    if humidity.max is not None:
        result["threshold.humidity.max"] = str(humidity.max)

    moisture = data.thresholds.moisture
    if moisture.default is not None:
        result["threshold.moisture.default"] = str(moisture.default)
    if moisture.plant_1 is not None:
        result["threshold.moisture.1"] = str(moisture.plant_1)
    if moisture.plant_2 is not None:
        result["threshold.moisture.2"] = str(moisture.plant_2)
    if moisture.plant_3 is not None:
        result["threshold.moisture.3"] = str(moisture.plant_3)

    notifications = data.notifications
    if notifications.enabled is not None:
        result["notification.enabled"] = "1" if notifications.enabled else "0"
    if notifications.backends is not None:
        result["notification.backends"] = ",".join(notifications.backends)

    cleanup = data.cleanup
    if cleanup.retentionDays is not None:
        result["cleanup.retention_days"] = str(cleanup.retentionDays)

    return result


def _format_pydantic_errors(errors: list[dict[str, Any]]) -> list[str]:
    """Format Pydantic validation errors into readable messages."""
    messages = []
    for error in errors:
        loc = " -> ".join(str(x) for x in error["loc"])
        msg = error["msg"]
        messages.append(f"{loc}: {msg}")
    return messages


@require_auth
async def get_admin_settings(request: Request) -> JSONResponse:
    """Get all admin-configurable settings."""
    db_settings = await get_all_settings()
    response_data = _db_settings_to_response(db_settings)
    return JSONResponse(response_data)


@require_auth
async def update_admin_settings(request: Request) -> JSONResponse:
    """Update admin settings."""
    try:
        raw_data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    try:
        data = AdminSettingsRequest.model_validate(raw_data)
    except Exception as e:
        if hasattr(e, "errors"):
            errors = _format_pydantic_errors(e.errors())
        else:
            errors = [str(e)]
        return JSONResponse({"errors": errors}, status_code=400)

    db_settings = _request_to_db_settings(data)
    if db_settings:
        await set_settings_batch(db_settings)
        logger.info("Admin settings updated: %s", list(db_settings.keys()))

    all_settings = await get_all_settings()
    response_data = _db_settings_to_response(all_settings)
    return JSONResponse(response_data)
