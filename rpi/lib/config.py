"""Centralized configuration for the RPi Gardener application."""

import operator
import re
from collections.abc import Callable
from enum import IntEnum, StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class NotificationBackend(StrEnum):
    GMAIL = "gmail"
    SLACK = "slack"


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
PICO_PLANT_ID_PATTERN = re.compile(r"^plant-(\d+)$")

# DHT22 sensor physical bounds
DHT22_BOUNDS = {
    MeasureName.TEMPERATURE: (-40, 80),
    MeasureName.HUMIDITY: (0, 100),
}


def _parse_bool(v: Any) -> bool:
    """Parse boolean from string '1'/'0' or actual bool."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v == "1"
    return bool(v)


BoolFromStr = Annotated[bool, BeforeValidator(_parse_bool)]


class GmailSettings(BaseModel):
    """Gmail notification settings."""

    model_config = ConfigDict(frozen=True)

    sender: str = ""
    recipients: str = ""
    username: str = ""
    password: str = ""
    subject: str = "Sensor alert!"


class SlackSettings(BaseModel):
    """Slack notification settings."""

    model_config = ConfigDict(frozen=True)

    webhook_url: str = ""


class ThresholdSettings(BaseModel):
    """Sensor threshold settings."""

    model_config = ConfigDict(frozen=True)

    max_temperature: int = 25
    min_temperature: int = 18
    max_humidity: int = 65
    min_humidity: int = 40
    min_moisture: int = 30
    plant_moisture_thresholds: dict[int, int] = {}

    def get_moisture_threshold(self, plant_id: int) -> int:
        """Get moisture threshold for a plant, falling back to default."""
        return self.plant_moisture_thresholds.get(plant_id, self.min_moisture)


class NotificationSettings(BaseModel):
    """Notification service settings."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    backends: list[str] = []
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

    retention_days: int = 3


class EventBusSettings(BaseModel):
    """Redis event bus settings."""

    model_config = ConfigDict(frozen=True)

    redis_url: str = "redis://localhost:6379/0"


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
    mock_sensors: BoolFromStr = False

    # Thresholds
    max_temperature: int = 25
    min_temperature: int = 18
    max_humidity: int = 65
    min_humidity: int = 40
    min_moisture: int = 30
    min_moisture_plant_1: int | None = None
    min_moisture_plant_2: int | None = None
    min_moisture_plant_3: int | None = None

    # Notifications
    enable_notification_service: BoolFromStr = False
    notification_backends: str = "gmail"
    gmail_sender: str = ""
    gmail_recipients: str = ""
    gmail_username: str = ""
    gmail_password: str = ""
    gmail_subject: str = "Sensor alert!"
    slack_webhook_url: str = ""
    email_max_retries: int = 3
    email_initial_backoff_sec: int = 2
    email_timeout_sec: int = 30

    # Pico
    pico_serial_port: str = "/dev/ttyACM0"
    pico_serial_baud: int = 115200
    pico_serial_timeout_sec: float = 30.0

    # Cleanup
    retention_days: int = 3

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    @property
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

    @property
    def notifications(self) -> NotificationSettings:
        """Get notification settings as nested object."""
        backends = [
            b.strip()
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
                subject=self.gmail_subject,
            ),
            slack=SlackSettings(webhook_url=self.slack_webhook_url),
            max_retries=self.email_max_retries,
            initial_backoff_sec=self.email_initial_backoff_sec,
            timeout_sec=self.email_timeout_sec,
        )

    @property
    def pico(self) -> PicoSettings:
        """Get Pico settings as nested object."""
        return PicoSettings(
            serial_port=self.pico_serial_port,
            serial_baud=self.pico_serial_baud,
            serial_timeout_sec=self.pico_serial_timeout_sec,
        )

    @property
    def display(self) -> DisplaySettings:
        """Get display settings."""
        return DisplaySettings()

    @property
    def polling(self) -> PollingSettings:
        """Get polling settings."""
        return PollingSettings()

    @property
    def cleanup(self) -> CleanupSettings:
        """Get cleanup settings."""
        return CleanupSettings(retention_days=self.retention_days)

    @property
    def eventbus(self) -> EventBusSettings:
        """Get event bus settings."""
        return EventBusSettings(redis_url=self.redis_url)

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        """Validate configuration values."""
        errors: list[str] = []

        if self.thresholds.min_temperature >= self.thresholds.max_temperature:
            errors.append(
                f"MIN_TEMPERATURE ({self.thresholds.min_temperature}) must be less than "
                f"MAX_TEMPERATURE ({self.thresholds.max_temperature})"
            )

        if self.thresholds.min_humidity >= self.thresholds.max_humidity:
            errors.append(
                f"MIN_HUMIDITY ({self.thresholds.min_humidity}) must be less than "
                f"MAX_HUMIDITY ({self.thresholds.max_humidity})"
            )

        temp_min, temp_max = DHT22_BOUNDS[MeasureName.TEMPERATURE]
        if not (
            temp_min
            <= self.thresholds.min_temperature
            < self.thresholds.max_temperature
            <= temp_max
        ):
            errors.append(
                f"Temperature thresholds must be within sensor bounds [{temp_min}, {temp_max}]"
            )

        hum_min, hum_max = DHT22_BOUNDS[MeasureName.HUMIDITY]
        if not (
            hum_min
            <= self.thresholds.min_humidity
            < self.thresholds.max_humidity
            <= hum_max
        ):
            errors.append(
                f"Humidity thresholds must be within sensor bounds [{hum_min}, {hum_max}]"
            )

        for plant_id, threshold in self.thresholds.plant_moisture_thresholds.items():
            if not (self.pico.moisture_min <= threshold <= self.pico.moisture_max):
                errors.append(
                    f"Moisture threshold for {plant_id} ({threshold}) must be "
                    f"between {self.pico.moisture_min} and {self.pico.moisture_max}"
                )

        if self.notifications.enabled:
            if NotificationBackend.GMAIL in self.notifications.backends:
                missing = []
                if not self.notifications.gmail.sender:
                    missing.append("GMAIL_SENDER")
                if not self.notifications.gmail.recipients:
                    missing.append("GMAIL_RECIPIENTS")
                if not self.notifications.gmail.username:
                    missing.append("GMAIL_USERNAME")
                if not self.notifications.gmail.password:
                    missing.append("GMAIL_PASSWORD")
                if missing:
                    errors.append(
                        f"Gmail enabled but missing: {', '.join(missing)}"
                    )

            if NotificationBackend.SLACK in self.notifications.backends:
                if not self.notifications.slack.webhook_url:
                    errors.append("Slack enabled but SLACK_WEBHOOK_URL is not set")

        if errors:
            raise ValueError(
                "Configuration validation failed:\n  - " + "\n  - ".join(errors)
            )

        return self


# Lazy-initialized settings (created on first access, not at import)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance, initializing on first call."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def set_settings(settings: Settings | None) -> None:
    """Override the global settings (primarily for testing)."""
    global _settings
    _settings = settings


def get_moisture_threshold(plant_id: int) -> int:
    """Get moisture threshold for a plant, falling back to default."""
    return get_settings().thresholds.get_moisture_threshold(plant_id)


def parse_pico_plant_id(raw_id: str) -> int | None:
    """Parse Pico's 'plant-N' format to integer N. Returns None if invalid."""
    match = PICO_PLANT_ID_PATTERN.match(raw_id)
    if match:
        return int(match.group(1))
    return None


type ThresholdRule = tuple[Callable[[float, float], bool], int]


def get_threshold_rules() -> dict[MeasureName, tuple[ThresholdRule, ...]]:
    """Get threshold rules based on current settings."""
    s = get_settings()
    return {
        MeasureName.TEMPERATURE: (
            (operator.lt, s.thresholds.min_temperature),
            (operator.gt, s.thresholds.max_temperature),
        ),
        MeasureName.HUMIDITY: (
            (operator.lt, s.thresholds.min_humidity),
            (operator.gt, s.thresholds.max_humidity),
        ),
    }


async def get_effective_thresholds() -> ThresholdSettings:
    """Get threshold settings with DB overrides applied."""
    from rpi.lib.db import get_all_settings

    db_settings = await get_all_settings()
    env_settings = get_settings()

    def get_int(key: str, default: int) -> int:
        val = db_settings.get(key)
        return int(val) if val is not None else default

    min_moisture = get_int(
        "threshold.moisture.default", env_settings.thresholds.min_moisture
    )
    plant_thresholds = {
        i: get_int(
            f"threshold.moisture.{i}",
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
    backends = (
        [b.strip() for b in backends_val.split(",") if b.strip()]
        if backends_val is not None
        else env_settings.notifications.backends
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


async def get_effective_cleanup() -> CleanupSettings:
    """Get cleanup settings with DB overrides applied."""
    from rpi.lib.db import get_all_settings

    db_settings = await get_all_settings()
    env_settings = get_settings()

    retention_val = db_settings.get("cleanup.retention_days")
    retention_days = (
        int(retention_val)
        if retention_val is not None
        else env_settings.cleanup.retention_days
    )

    return CleanupSettings(retention_days=retention_days)
