"""Centralized configuration for the RPi Gardener application."""

import os
import re
from enum import IntEnum, StrEnum
from functools import cached_property, lru_cache
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    SecretStr,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class NotificationBackend(StrEnum):
    GMAIL = "gmail"
    SLACK = "slack"


class Unit(StrEnum):
    """Measurement units for sensor readings."""

    CELSIUS = "°C"
    PERCENT = "%"


class ThresholdType(StrEnum):
    """Type of threshold being checked."""

    MIN = "min"  # Alert when value < threshold
    MAX = "max"  # Alert when value > threshold


class MeasureName(StrEnum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"


class PlantId(IntEnum):
    PLANT_1 = 1
    PLANT_2 = 2
    PLANT_3 = 3


# Type alias for raw plant ID values (used when parsing from Pico data)
type PlantIdValue = int


# Patterns
_PICO_PLANT_ID_PATTERN = re.compile(r"^plant-(\d+)$")

# Hysteresis offsets for alert recovery (prevents flapping)
# Alert triggers at threshold, clears at threshold ± hysteresis
_HYSTERESIS_TEMPERATURE = 1  # °C
_HYSTERESIS_HUMIDITY = 3  # %
_HYSTERESIS_MOISTURE = 3  # %

# DHT22 sensor physical bounds
DHT22_BOUNDS = {
    MeasureName.TEMPERATURE: (-40, 80),
    MeasureName.HUMIDITY: (0, 100),
}

# Valid DB settings keys for type safety
type SettingsKey = Literal[
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
]


def _parse_bool(v: Any) -> bool:
    """Parse boolean from string '1'/'0' or actual bool."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v == "1"
    return bool(v)


_BoolFromStr = Annotated[bool, BeforeValidator(_parse_bool)]


def _validate_email_or_empty(v: str) -> str:
    """Validate email format, allowing empty string."""
    if not v:
        return v
    from pydantic import validate_email

    validate_email(v)
    return v


def _validate_http_url_or_empty(v: str) -> str:
    """Validate HTTP URL format, allowing empty string."""
    if not v:
        return v
    HttpUrl(v)
    return v


def _detect_pico_port() -> str | None:
    """Auto-detect Pico serial port (ttyACM0 or ttyACM1)."""
    for port in ("/dev/ttyACM0", "/dev/ttyACM1"):
        if os.path.exists(port):
            return port
    return None


_EmailOrEmpty = Annotated[str, AfterValidator(_validate_email_or_empty)]
_HttpUrlOrEmpty = Annotated[str, AfterValidator(_validate_http_url_or_empty)]


class GmailSettings(BaseModel):
    """Gmail notification settings."""

    model_config = ConfigDict(frozen=True)

    sender: str = ""
    recipients: str = ""  # Comma-separated list, validated separately
    username: _EmailOrEmpty = ""
    password: SecretStr = SecretStr("")


class SlackSettings(BaseModel):
    """Slack notification settings."""

    model_config = ConfigDict(frozen=True)

    webhook_url: _HttpUrlOrEmpty = ""


class ThresholdSettings(BaseModel):
    """Sensor threshold settings."""

    model_config = ConfigDict(frozen=True)

    max_temperature: int = 25
    min_temperature: int = 18
    max_humidity: int = 65
    min_humidity: int = 40
    min_moisture: int = 30
    plant_moisture_thresholds: dict[int, int] = {}

    @property
    def moisture_hysteresis(self) -> int:
        """Hysteresis offset for moisture alerts."""
        return _HYSTERESIS_MOISTURE

    def get_moisture_threshold(self, plant_id: int) -> int:
        """Get moisture threshold for a plant, falling back to default."""
        return self.plant_moisture_thresholds.get(plant_id, self.min_moisture)


class NotificationSettings(BaseModel):
    """Notification service settings."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    backends: list[NotificationBackend] = []
    gmail: GmailSettings = GmailSettings()
    slack: SlackSettings = SlackSettings()
    max_retries: int = 3
    initial_backoff_sec: int = 2
    timeout_sec: int = 30


class PicoSettings(BaseModel):
    """Pico serial connection settings."""

    model_config = ConfigDict(frozen=True)

    serial_port: str = "/dev/ttyACM0"
    serial_baud: int = 115200
    serial_timeout_sec: float = 30.0
    moisture_min: float = 0.0
    moisture_max: float = 100.0
    plant_id_max_length: int = 64


class DisplaySettings(BaseModel):
    """OLED display settings."""

    model_config = ConfigDict(frozen=True)

    width: int = 128
    height: int = 64
    font_size: int = 17
    font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    text_x_offset: int = 23
    text_y_temp: int = 0
    text_y_humidity: int = 20


class PollingSettings(BaseModel):
    """Polling service settings."""

    model_config = ConfigDict(frozen=True)

    frequency_sec: int = 2


class CleanupSettings(BaseModel):
    """Database cleanup settings (used by cron job)."""

    model_config = ConfigDict(frozen=True)

    retention_days: int = 7


class EventBusSettings(BaseModel):
    """Redis event bus settings."""

    model_config = ConfigDict(frozen=True)

    redis_url: str = "redis://localhost:6379/0"


class SmartPlugSettings(BaseModel):
    """TP-Link Kasa smart plug settings for humidity control."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    host: str = ""  # IP address or hostname of the Kasa device


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    db_path: str = "dht.sqlite3"
    db_timeout_sec: float = 30.0

    # Sensors
    mock_sensors: _BoolFromStr = False

    # Thresholds (DHT22 bounds: temp -40 to 80, humidity 0 to 100)
    max_temperature: int = Field(default=25, ge=-40, le=80)
    min_temperature: int = Field(default=18, ge=-40, le=80)
    max_humidity: int = Field(default=65, ge=0, le=100)
    min_humidity: int = Field(default=40, ge=0, le=100)
    min_moisture: int = Field(default=30, ge=0, le=100)
    min_moisture_plant_1: int | None = Field(default=None, ge=0, le=100)
    min_moisture_plant_2: int | None = Field(default=None, ge=0, le=100)
    min_moisture_plant_3: int | None = Field(default=None, ge=0, le=100)

    # Notifications
    enable_notification_service: _BoolFromStr = False
    notification_backends: str = "gmail"
    gmail_sender: str = ""
    gmail_recipients: str = ""  # Comma-separated list
    gmail_username: _EmailOrEmpty = ""
    gmail_password: SecretStr = SecretStr("")
    slack_webhook_url: _HttpUrlOrEmpty = ""
    email_max_retries: int = Field(default=3, ge=0)
    email_initial_backoff_sec: int = Field(default=2, ge=0)
    email_timeout_sec: int = Field(default=30, ge=1)

    # Pico
    pico_serial_port: str = "auto"
    pico_serial_baud: int = Field(default=115200, gt=0)
    pico_serial_timeout_sec: float = Field(default=30.0, gt=0)

    # Cleanup
    retention_days: int = Field(default=7, ge=1)

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Smart plug (Kasa)
    smartplug_enabled: _BoolFromStr = False
    smartplug_host: str = ""

    @cached_property
    def thresholds(self) -> ThresholdSettings:
        """Get threshold settings as nested object."""
        plant_thresholds = {}
        for plant_id, val in [
            (1, self.min_moisture_plant_1),
            (2, self.min_moisture_plant_2),
            (3, self.min_moisture_plant_3),
        ]:
            plant_thresholds[plant_id] = (
                val if val is not None else self.min_moisture
            )
        return ThresholdSettings(
            max_temperature=self.max_temperature,
            min_temperature=self.min_temperature,
            max_humidity=self.max_humidity,
            min_humidity=self.min_humidity,
            min_moisture=self.min_moisture,
            plant_moisture_thresholds=plant_thresholds,
        )

    @cached_property
    def notifications(self) -> NotificationSettings:
        """Get notification settings as nested object."""
        backends = [
            NotificationBackend(b.strip())
            for b in self.notification_backends.split(",")
            if b.strip()
        ]
        return NotificationSettings(
            enabled=self.enable_notification_service,
            backends=backends,
            gmail=GmailSettings(
                sender=self.gmail_sender,
                recipients=self.gmail_recipients,
                username=self.gmail_username,
                password=self.gmail_password,
            ),
            slack=SlackSettings(webhook_url=self.slack_webhook_url),
            max_retries=self.email_max_retries,
            initial_backoff_sec=self.email_initial_backoff_sec,
            timeout_sec=self.email_timeout_sec,
        )

    @cached_property
    def pico(self) -> PicoSettings:
        """Get Pico settings as nested object."""
        serial_port = self.pico_serial_port
        # Auto-detect if set to "auto" or configured port doesn't exist
        if serial_port == "auto" or not os.path.exists(serial_port):
            serial_port = _detect_pico_port() or self.pico_serial_port
        return PicoSettings(
            serial_port=serial_port,
            serial_baud=self.pico_serial_baud,
            serial_timeout_sec=self.pico_serial_timeout_sec,
        )

    @cached_property
    def display(self) -> DisplaySettings:
        """Get display settings."""
        return DisplaySettings()

    @cached_property
    def polling(self) -> PollingSettings:
        """Get polling settings."""
        return PollingSettings()

    @cached_property
    def cleanup(self) -> CleanupSettings:
        """Get cleanup settings."""
        return CleanupSettings(retention_days=self.retention_days)

    @cached_property
    def eventbus(self) -> EventBusSettings:
        """Get event bus settings."""
        return EventBusSettings(redis_url=self.redis_url)

    @cached_property
    def smartplug(self) -> SmartPlugSettings:
        """Get smart plug settings."""
        return SmartPlugSettings(
            enabled=self.smartplug_enabled,
            host=self.smartplug_host,
        )

    @model_validator(mode="after")
    def validate_settings(self) -> Self:
        """Validate cross-field configuration constraints."""
        errors: list[str] = []

        # Cross-field comparisons (individual bounds handled by Field constraints)
        if self.min_temperature >= self.max_temperature:
            errors.append(
                f"MIN_TEMPERATURE ({self.min_temperature}) must be less than "
                f"MAX_TEMPERATURE ({self.max_temperature})"
            )

        if self.min_humidity >= self.max_humidity:
            errors.append(
                f"MIN_HUMIDITY ({self.min_humidity}) must be less than "
                f"MAX_HUMIDITY ({self.max_humidity})"
            )

        # Notification credential checks
        if self.enable_notification_service:
            backends = [
                b.strip()
                for b in self.notification_backends.split(",")
                if b.strip()
            ]

            if NotificationBackend.GMAIL in backends:
                missing = []
                if not self.gmail_sender:
                    missing.append("GMAIL_SENDER")
                if not self.gmail_recipients:
                    missing.append("GMAIL_RECIPIENTS")
                if not self.gmail_username:
                    missing.append("GMAIL_USERNAME")
                if not self.gmail_password.get_secret_value():
                    missing.append("GMAIL_PASSWORD")
                if missing:
                    errors.append(
                        f"Gmail enabled but missing: {', '.join(missing)}"
                    )

            if NotificationBackend.SLACK in backends:
                if not self.slack_webhook_url:
                    errors.append(
                        "Slack enabled but SLACK_WEBHOOK_URL is not set"
                    )

        if errors:
            raise ValueError(
                "Configuration validation failed:\n  - "
                + "\n  - ".join(errors)
            )

        return self


# Test-only: allows tests to inject custom Settings without modifying environment
# variables or clearing the lru_cache. Set via conftest.set_settings().
_settings_override: Settings | None = None


@lru_cache(maxsize=1)
def _load_settings() -> Settings:
    """Load settings from environment (cached)."""
    return Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    if _settings_override is not None:
        return _settings_override
    return _load_settings()


def parse_pico_plant_id(raw_id: str) -> int | None:
    """Parse Pico's 'plant-N' format to integer N. Returns None if invalid."""
    match = _PICO_PLANT_ID_PATTERN.match(raw_id)
    if match:
        return int(match.group(1))
    return None


type _ThresholdRule = tuple[
    ThresholdType, int, float
]  # (type, value, hysteresis)


async def get_threshold_rules_async() -> dict[
    MeasureName, tuple[_ThresholdRule, ...]
]:
    """Get threshold rules with DB overrides applied.

    This checks the database for runtime setting changes made via
    the admin API, falling back to environment variable defaults.

    Returns a dict mapping measure name to a tuple of (threshold_type, value, hysteresis).
    """
    thresholds = await get_effective_thresholds()
    return {
        MeasureName.TEMPERATURE: (
            (
                ThresholdType.MIN,
                thresholds.min_temperature,
                _HYSTERESIS_TEMPERATURE,
            ),
            (
                ThresholdType.MAX,
                thresholds.max_temperature,
                _HYSTERESIS_TEMPERATURE,
            ),
        ),
        MeasureName.HUMIDITY: (
            (
                ThresholdType.MIN,
                thresholds.min_humidity,
                _HYSTERESIS_HUMIDITY,
            ),
            (
                ThresholdType.MAX,
                thresholds.max_humidity,
                _HYSTERESIS_HUMIDITY,
            ),
        ),
    }


async def get_effective_thresholds() -> ThresholdSettings:
    """Get threshold settings with DB overrides applied."""
    from rpi.lib.db import get_all_settings

    db_settings = await get_all_settings()
    env_settings = get_settings()

    def get_int(key: SettingsKey, default: int) -> int:
        val = db_settings.get(key)
        return int(val) if val is not None else default

    min_moisture = get_int(
        "threshold.moisture.default", env_settings.thresholds.min_moisture
    )
    moisture_keys: dict[int, SettingsKey] = {
        1: "threshold.moisture.1",
        2: "threshold.moisture.2",
        3: "threshold.moisture.3",
    }
    plant_thresholds = {
        i: get_int(
            moisture_keys[i],
            env_settings.thresholds.get_moisture_threshold(i),
        )
        for i in (1, 2, 3)
    }

    return ThresholdSettings(
        max_temperature=get_int(
            "threshold.temperature.max",
            env_settings.thresholds.max_temperature,
        ),
        min_temperature=get_int(
            "threshold.temperature.min",
            env_settings.thresholds.min_temperature,
        ),
        max_humidity=get_int(
            "threshold.humidity.max", env_settings.thresholds.max_humidity
        ),
        min_humidity=get_int(
            "threshold.humidity.min", env_settings.thresholds.min_humidity
        ),
        min_moisture=min_moisture,
        plant_moisture_thresholds=plant_thresholds,
    )


async def get_effective_notifications() -> NotificationSettings:
    """Get notification settings with DB overrides applied."""
    from rpi.lib.db import get_all_settings

    db_settings = await get_all_settings()
    env_settings = get_settings()

    enabled_val = db_settings.get("notification.enabled")
    enabled = (
        enabled_val == "1"
        if enabled_val is not None
        else env_settings.notifications.enabled
    )

    backends_val = db_settings.get("notification.backends")
    backends: list[NotificationBackend] = (
        [
            NotificationBackend(b.strip())
            for b in backends_val.split(",")
            if b.strip()
        ]
        if backends_val is not None
        else list(env_settings.notifications.backends)
    )

    return NotificationSettings(
        enabled=enabled,
        backends=backends,
        gmail=env_settings.notifications.gmail,
        slack=env_settings.notifications.slack,
        max_retries=env_settings.notifications.max_retries,
        initial_backoff_sec=env_settings.notifications.initial_backoff_sec,
        timeout_sec=env_settings.notifications.timeout_sec,
    )
