import operator
from enum import IntEnum, StrEnum
from os import environ
from pathlib import Path

from dotenv import load_dotenv
from sqlitey import DbPathConfig

load_dotenv()

POLLING_FREQUENCY_SEC = 2

DB_CONFIG = DbPathConfig(
    database="dht.sqlite3",
    sql_templates_dir=Path(__file__).resolve().parent / "sql"
)


class MeasureName(StrEnum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"


# DHT22 sensor reading bounds, a reading outside of those, would mean
# an error has happened, and the reading would need to be retried.
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


NOTIFICATION_SERVICE_ENABLED = bool(
    environ.get("ENABLE_NOTIFICATION_SERVICE", "0") == "1")


class GmailConfig:
    SENDER = environ["GMAIL_SENDER"]
    RECIPIENTS = environ["GMAIL_RECIPIENTS"]
    USERNAME = environ["GMAIL_USERNAME"]
    PASSWORD = environ["GMAIL_PASSWORD"]
    SUBJECT = environ.get("GMAIL_SUBJECT", "Sensor alert!")


FLASK_SECRET_KEY = environ["SECRET_KEY"]
