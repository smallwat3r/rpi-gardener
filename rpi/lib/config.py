"""Centralized configuration for the RPi Gardener application."""
import operator
import re
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from os import environ
from typing import Callable, TypeAlias

from dotenv import load_dotenv

load_dotenv()


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


# Patterns
PICO_PLANT_ID_PATTERN = re.compile(r"^plant-(\d+)$")

# DHT22 sensor physical bounds
DHT22_BOUNDS = {
    MeasureName.TEMPERATURE: (-40, 80),
    MeasureName.HUMIDITY: (0, 100)
}


@dataclass(frozen=True)
class GmailSettings:
    """Gmail notification settings."""
    sender: str = ""
    recipients: str = ""
    username: str = ""
    password: str = ""
    subject: str = "Sensor alert!"

    @classmethod
    def from_env(cls) -> "GmailSettings":
        return cls(
            sender=environ.get("GMAIL_SENDER", ""),
            recipients=environ.get("GMAIL_RECIPIENTS", ""),
            username=environ.get("GMAIL_USERNAME", ""),
            password=environ.get("GMAIL_PASSWORD", ""),
            subject=environ.get("GMAIL_SUBJECT", "Sensor alert!"),
        )


@dataclass(frozen=True)
class SlackSettings:
    """Slack notification settings."""
    webhook_url: str = ""

    @classmethod
    def from_env(cls) -> "SlackSettings":
        return cls(webhook_url=environ.get("SLACK_WEBHOOK_URL", ""))


@dataclass(frozen=True)
class ThresholdSettings:
    """Sensor threshold settings."""
    max_temperature: int = 25
    min_temperature: int = 18
    max_humidity: int = 65
    min_humidity: int = 40
    min_moisture: int = 30
    plant_moisture_thresholds: dict[int, int] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "ThresholdSettings":
        min_moisture = int(environ.get("MIN_MOISTURE", 30))
        plant_thresholds = {
            plant_id: int(environ.get(f"MIN_MOISTURE_PLANT_{plant_id.value}", min_moisture))
            for plant_id in PlantId
        }
        return cls(
            max_temperature=int(environ.get("MAX_TEMPERATURE", 25)),
            min_temperature=int(environ.get("MIN_TEMPERATURE", 18)),
            max_humidity=int(environ.get("MAX_HUMIDITY", 65)),
            min_humidity=int(environ.get("MIN_HUMIDITY", 40)),
            min_moisture=min_moisture,
            plant_moisture_thresholds=plant_thresholds,
        )

    def get_moisture_threshold(self, plant_id: int) -> int:
        """Get moisture threshold for a plant, falling back to default."""
        return self.plant_moisture_thresholds.get(plant_id, self.min_moisture)


@dataclass(frozen=True)
class NotificationSettings:
    """Notification service settings."""
    enabled: bool = False
    backends: list[str] = field(default_factory=list)
    gmail: GmailSettings = field(default_factory=GmailSettings)
    slack: SlackSettings = field(default_factory=SlackSettings)
    max_retries: int = 3
    initial_backoff_sec: int = 2
    timeout_sec: int = 30

    @classmethod
    def from_env(cls) -> "NotificationSettings":
        backends_str = environ.get("NOTIFICATION_BACKENDS", "gmail")
        backends = [b.strip() for b in backends_str.split(",") if b.strip()]
        return cls(
            enabled=environ.get("ENABLE_NOTIFICATION_SERVICE", "0") == "1",
            backends=backends,
            gmail=GmailSettings.from_env(),
            slack=SlackSettings.from_env(),
            max_retries=int(environ.get("EMAIL_MAX_RETRIES", 3)),
            initial_backoff_sec=int(environ.get("EMAIL_INITIAL_BACKOFF_SEC", 2)),
            timeout_sec=int(environ.get("EMAIL_TIMEOUT_SEC", 30)),
        )


@dataclass(frozen=True)
class PicoSettings:
    """Pico serial connection settings."""
    serial_port: str = "/dev/ttyACM0"
    serial_baud: int = 115200
    serial_timeout_sec: float = 30.0
    moisture_min: float = 0.0
    moisture_max: float = 100.0
    plant_id_max_length: int = 64

    @classmethod
    def from_env(cls) -> "PicoSettings":
        return cls(
            serial_port=environ.get("PICO_SERIAL_PORT", "/dev/ttyACM0"),
            serial_baud=int(environ.get("PICO_SERIAL_BAUD", "115200")),
            serial_timeout_sec=float(environ.get("PICO_SERIAL_TIMEOUT_SEC", "30.0")),
        )


@dataclass(frozen=True)
class DisplaySettings:
    """OLED display settings."""
    width: int = 128
    height: int = 64
    font_size: int = 17
    font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    text_x_offset: int = 23
    text_y_temp: int = 0
    text_y_humidity: int = 20


@dataclass(frozen=True)
class PollingSettings:
    """Polling service settings."""
    frequency_sec: int = 2
    cleanup_interval_cycles: int = 1800  # ~1 hour at 2s intervals
    cleanup_retention_days: int = 3


@dataclass(frozen=True)
class Settings:
    """Application settings container."""
    db_path: str = "dht.sqlite3"
    db_timeout_sec: float = 30.0
    thresholds: ThresholdSettings = field(default_factory=ThresholdSettings)
    notifications: NotificationSettings = field(default_factory=NotificationSettings)
    pico: PicoSettings = field(default_factory=PicoSettings)
    display: DisplaySettings = field(default_factory=DisplaySettings)
    polling: PollingSettings = field(default_factory=PollingSettings)

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        return cls(
            db_path=environ.get("DB_PATH", "dht.sqlite3"),
            db_timeout_sec=float(environ.get("DB_TIMEOUT_SEC", "30.0")),
            thresholds=ThresholdSettings.from_env(),
            notifications=NotificationSettings.from_env(),
            pico=PicoSettings.from_env(),
            display=DisplaySettings(),
            polling=PollingSettings(),
        )


# Lazy-initialized settings (created on first access, not at import)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance, initializing on first call.

    This lazy initialization allows tests to set up environment variables
    before settings are read, and supports settings override via set_settings().
    """
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
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


ThresholdRule: TypeAlias = tuple[Callable[[float, float], bool], int]


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


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""


def validate_config() -> None:
    """Validate configuration values at startup.

    Raises ConfigurationError if any validation fails.
    """
    errors: list[str] = []
    s = get_settings()

    # Threshold sanity checks
    if s.thresholds.min_temperature >= s.thresholds.max_temperature:
        errors.append(
            f"MIN_TEMPERATURE ({s.thresholds.min_temperature}) must be less than "
            f"MAX_TEMPERATURE ({s.thresholds.max_temperature})"
        )

    if s.thresholds.min_humidity >= s.thresholds.max_humidity:
        errors.append(
            f"MIN_HUMIDITY ({s.thresholds.min_humidity}) must be less than "
            f"MAX_HUMIDITY ({s.thresholds.max_humidity})"
        )

    # DHT22 bounds validation
    temp_min, temp_max = DHT22_BOUNDS[MeasureName.TEMPERATURE]
    if not (temp_min <= s.thresholds.min_temperature < s.thresholds.max_temperature <= temp_max):
        errors.append(
            f"Temperature thresholds must be within sensor bounds [{temp_min}, {temp_max}]"
        )

    hum_min, hum_max = DHT22_BOUNDS[MeasureName.HUMIDITY]
    if not (hum_min <= s.thresholds.min_humidity < s.thresholds.max_humidity <= hum_max):
        errors.append(
            f"Humidity thresholds must be within sensor bounds [{hum_min}, {hum_max}]"
        )

    # Moisture thresholds validation
    for plant_id, threshold in s.thresholds.plant_moisture_thresholds.items():
        if not (s.pico.moisture_min <= threshold <= s.pico.moisture_max):
            errors.append(
                f"Moisture threshold for {plant_id} ({threshold}) must be "
                f"between {s.pico.moisture_min} and {s.pico.moisture_max}"
            )

    # Notification config validation
    if s.notifications.enabled:
        if NotificationBackend.GMAIL in s.notifications.backends:
            missing = []
            if not s.notifications.gmail.sender:
                missing.append("GMAIL_SENDER")
            if not s.notifications.gmail.recipients:
                missing.append("GMAIL_RECIPIENTS")
            if not s.notifications.gmail.username:
                missing.append("GMAIL_USERNAME")
            if not s.notifications.gmail.password:
                missing.append("GMAIL_PASSWORD")
            if missing:
                errors.append(f"Gmail enabled but missing: {', '.join(missing)}")

        if NotificationBackend.SLACK in s.notifications.backends:
            if not s.notifications.slack.webhook_url:
                errors.append("Slack enabled but SLACK_WEBHOOK_URL is not set")

    if errors:
        raise ConfigurationError(
            "Configuration validation failed:\n  - " + "\n  - ".join(errors)
        )
