"""Centralized configuration for the RPi Gardener application."""
import operator
import re
import sqlite3
from datetime import datetime
from enum import IntEnum, StrEnum
from os import environ
from pathlib import Path

from dotenv import load_dotenv
from sqlitey import Db, DbPathConfig

load_dotenv()


# SQLite datetime adapter - Python 3.12+ removed the default adapters
def _adapt_datetime(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


sqlite3.register_adapter(datetime, _adapt_datetime)

# Environment variables
DB_PATH = environ.get("DB_PATH", "dht.sqlite3")
MAX_TEMPERATURE = int(environ.get("MAX_TEMPERATURE", 25))
MIN_TEMPERATURE = int(environ.get("MIN_TEMPERATURE", 18))
MAX_HUMIDITY = int(environ.get("MAX_HUMIDITY", 65))
MIN_HUMIDITY = int(environ.get("MIN_HUMIDITY", 40))
MIN_MOISTURE = int(environ.get("MIN_MOISTURE", 30))
NOTIFICATION_SERVICE_ENABLED = environ.get("ENABLE_NOTIFICATION_SERVICE", "0") == "1"


class NotificationBackend(StrEnum):
    GMAIL = "gmail"
    SLACK = "slack"


NOTIFICATION_BACKENDS = [
    b.strip() for b in environ.get("NOTIFICATION_BACKENDS", "gmail").split(",") if b.strip()
]


class GmailConfig:
    SENDER = environ.get("GMAIL_SENDER", "")
    RECIPIENTS = environ.get("GMAIL_RECIPIENTS", "")
    USERNAME = environ.get("GMAIL_USERNAME", "")
    PASSWORD = environ.get("GMAIL_PASSWORD", "")
    SUBJECT = environ.get("GMAIL_SUBJECT", "Sensor alert!")


class SlackConfig:
    WEBHOOK_URL = environ.get("SLACK_WEBHOOK_URL", "")


# Database
_DB_CONFIG = DbPathConfig(
    database=DB_PATH,
    sql_templates_dir=Path(__file__).resolve().parent / "sql"
)


def db_with_config(**kwargs) -> Db:
    """Shortcut to load db with pre-configured config."""
    return Db.from_config(_DB_CONFIG, **kwargs)


# Polling
POLLING_FREQUENCY_SEC = 2
CLEANUP_INTERVAL_CYCLES = 1800  # Run cleanup every N poll cycles (~1 hour at 2s intervals)
CLEANUP_RETENTION_DAYS = 3


# DHT22 Sensor
class MeasureName(StrEnum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"


DHT22_BOUNDS = {
    MeasureName.TEMPERATURE: (-40, 80),
    MeasureName.HUMIDITY: (0, 100)
}


class Threshold(IntEnum):
    MAX_TEMPERATURE = MAX_TEMPERATURE
    MIN_TEMPERATURE = MIN_TEMPERATURE
    MAX_HUMIDITY = MAX_HUMIDITY
    MIN_HUMIDITY = MIN_HUMIDITY


THRESHOLD_RULES = {
    MeasureName.TEMPERATURE: (
        (operator.lt, Threshold.MIN_TEMPERATURE),
        (operator.gt, Threshold.MAX_TEMPERATURE),
    ),
    MeasureName.HUMIDITY: (
        (operator.lt, Threshold.MIN_HUMIDITY),
        (operator.gt, Threshold.MAX_HUMIDITY),
    ),
}


# Pico
PLANT_IDS = ["plant-1", "plant-2", "plant-3"]
MOISTURE_MIN = 0.0
MOISTURE_MAX = 100.0
PLANT_ID_MAX_LENGTH = 64
PLANT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
PICO_SERIAL_PORT = environ.get("PICO_SERIAL_PORT", "/dev/ttyACM0")
PICO_SERIAL_BAUD = int(environ.get("PICO_SERIAL_BAUD", "115200"))


def _env_key(plant_id: str) -> str:
    """Convert plant_id to env var name (e.g., plant-1 -> MIN_MOISTURE_PLANT_1)."""
    return f"MIN_MOISTURE_{plant_id.upper().replace('-', '_')}"


PLANT_MOISTURE_THRESHOLDS = {
    plant_id: int(environ.get(_env_key(plant_id), MIN_MOISTURE))
    for plant_id in PLANT_IDS
}


def get_moisture_threshold(plant_id: str) -> int:
    """Get moisture threshold for a plant, falling back to default."""
    return PLANT_MOISTURE_THRESHOLDS.get(plant_id, MIN_MOISTURE)


# OLED Display
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64
DISPLAY_FONT_SIZE = 17
DISPLAY_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
DISPLAY_TEXT_X_OFFSET = 23
DISPLAY_TEXT_Y_TEMP = 0
DISPLAY_TEXT_Y_HUMIDITY = 20


# Email
EMAIL_MAX_RETRIES = 3
EMAIL_INITIAL_BACKOFF_SEC = 2
EMAIL_TIMEOUT_SEC = 30


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""


def validate_config() -> None:
    """Validate configuration values at startup.

    Raises ConfigurationError if any validation fails.
    """
    errors: list[str] = []

    # Threshold sanity checks
    if MIN_TEMPERATURE >= MAX_TEMPERATURE:
        errors.append(
            f"MIN_TEMPERATURE ({MIN_TEMPERATURE}) must be less than "
            f"MAX_TEMPERATURE ({MAX_TEMPERATURE})"
        )

    if MIN_HUMIDITY >= MAX_HUMIDITY:
        errors.append(
            f"MIN_HUMIDITY ({MIN_HUMIDITY}) must be less than "
            f"MAX_HUMIDITY ({MAX_HUMIDITY})"
        )

    # DHT22 bounds validation
    temp_min, temp_max = DHT22_BOUNDS[MeasureName.TEMPERATURE]
    if not (temp_min <= MIN_TEMPERATURE < MAX_TEMPERATURE <= temp_max):
        errors.append(
            f"Temperature thresholds must be within sensor bounds [{temp_min}, {temp_max}]"
        )

    hum_min, hum_max = DHT22_BOUNDS[MeasureName.HUMIDITY]
    if not (hum_min <= MIN_HUMIDITY < MAX_HUMIDITY <= hum_max):
        errors.append(
            f"Humidity thresholds must be within sensor bounds [{hum_min}, {hum_max}]"
        )

    # Moisture thresholds validation
    for plant_id, threshold in PLANT_MOISTURE_THRESHOLDS.items():
        if not (MOISTURE_MIN <= threshold <= MOISTURE_MAX):
            errors.append(
                f"Moisture threshold for {plant_id} ({threshold}) must be "
                f"between {MOISTURE_MIN} and {MOISTURE_MAX}"
            )

    # Notification config validation
    if NOTIFICATION_SERVICE_ENABLED:
        if NotificationBackend.GMAIL in NOTIFICATION_BACKENDS:
            missing = []
            if not GmailConfig.SENDER:
                missing.append("GMAIL_SENDER")
            if not GmailConfig.RECIPIENTS:
                missing.append("GMAIL_RECIPIENTS")
            if not GmailConfig.USERNAME:
                missing.append("GMAIL_USERNAME")
            if not GmailConfig.PASSWORD:
                missing.append("GMAIL_PASSWORD")
            if missing:
                errors.append(f"Gmail enabled but missing: {', '.join(missing)}")

        if NotificationBackend.SLACK in NOTIFICATION_BACKENDS:
            if not SlackConfig.WEBHOOK_URL:
                errors.append("Slack enabled but SLACK_WEBHOOK_URL is not set")

    if errors:
        raise ConfigurationError(
            "Configuration validation failed:\n  - " + "\n  - ".join(errors)
        )
