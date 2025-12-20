"""Centralized configuration for the RPi Gardener application."""
import operator
import re
from enum import IntEnum, StrEnum
from os import environ
from pathlib import Path

from dotenv import load_dotenv
from sqlitey import Db, DbPathConfig

load_dotenv()


# =============================================================================
# Database Configuration
# =============================================================================

_DB_CONFIG = DbPathConfig(
    database="dht.sqlite3",
    sql_templates_dir=Path(__file__).resolve().parent / "sql"
)


def db_with_config(**kwargs) -> Db:
    """Shortcut to load db with pre-configured config."""
    return Db.from_config(_DB_CONFIG, **kwargs)


# =============================================================================
# Polling Configuration
# =============================================================================

POLLING_FREQUENCY_SEC = 2

# Cleanup: 1 in N chance to run cleanup on each poll cycle
CLEANUP_PROBABILITY_DENOMINATOR = 10
CLEANUP_RETENTION_DAYS = 3


# =============================================================================
# DHT22 Sensor Configuration
# =============================================================================

class MeasureName(StrEnum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"


# DHT22 sensor reading bounds - readings outside these are invalid
DHT22_BOUNDS = {
    MeasureName.TEMPERATURE: (-40, 80),
    MeasureName.HUMIDITY: (0, 100)
}


class Threshold(IntEnum):
    MAX_TEMPERATURE = int(environ.get("MAX_TEMPERATURE", 25))
    MIN_TEMPERATURE = int(environ.get("MIN_TEMPERATURE", 18))
    MAX_HUMIDITY = int(environ.get("MAX_HUMIDITY", 65))
    MIN_HUMIDITY = int(environ.get("MIN_HUMIDITY", 40))


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


# =============================================================================
# Pico API Configuration
# =============================================================================

MOISTURE_MIN = 0.0
MOISTURE_MAX = 100.0
PLANT_ID_MAX_LENGTH = 64
# Only allow alphanumeric, hyphens, and underscores to prevent XSS
PLANT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


# =============================================================================
# OLED Display Configuration
# =============================================================================

DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64
DISPLAY_FONT_SIZE = 17
DISPLAY_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
DISPLAY_TEXT_X_OFFSET = 23
DISPLAY_TEXT_Y_TEMP = 0
DISPLAY_TEXT_Y_HUMIDITY = 20


# =============================================================================
# Notification Configuration
# =============================================================================

NOTIFICATION_SERVICE_ENABLED = environ.get("ENABLE_NOTIFICATION_SERVICE", "0") == "1"

# Email retry settings
EMAIL_MAX_RETRIES = 3
EMAIL_INITIAL_BACKOFF_SEC = 2
EMAIL_TIMEOUT_SEC = 30


class GmailConfig:
    SENDER = environ.get("GMAIL_SENDER", "")
    RECIPIENTS = environ.get("GMAIL_RECIPIENTS", "")
    USERNAME = environ.get("GMAIL_USERNAME", "")
    PASSWORD = environ.get("GMAIL_PASSWORD", "")
    SUBJECT = environ.get("GMAIL_SUBJECT", "Sensor alert!")


# =============================================================================
# Flask Configuration
# =============================================================================

FLASK_SECRET_KEY = environ["SECRET_KEY"]
