from enum import IntEnum

POLLING_FREQUENCY_SEC = 2


class Threshold(IntEnum):
    MAX_TEMPERATURE = 25
    MIN_TEMPERATURE = 18
    MAX_HUMIDITY = 65
    MIN_HUMIDITY = 40