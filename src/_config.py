import operator
from enum import IntEnum, StrEnum
from os import environ

from dotenv import load_dotenv

load_dotenv()

POLLING_FREQUENCY_SEC = 2


class _MeasureName(StrEnum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"


class Unit(StrEnum):
    CELCIUS = "c"
    PERCENT = "%"


class Threshold(IntEnum):
    MAX_TEMPERATURE = int(environ.get("MAX_TEMPERATURE", 25))
    MIN_TEMPERATURE = int(environ.get("MIN_TEMPERATURE", 18))
    MAX_HUMIDITY = int(environ.get("MAX_HUMIDITY", 65))
    MIN_HUMIDITY = int(environ.get("MIN_HUMIDITY", 40))


THRESHOLD_RULES = {
    _MeasureName.TEMPERATURE: (
        (operator.lt, Threshold.MIN_TEMPERATURE),
        (operator.gt, Threshold.MAX_TEMPERATURE),
    ),
    _MeasureName.HUMIDITY: (
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
