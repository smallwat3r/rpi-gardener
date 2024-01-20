import operator
from enum import IntEnum
from typing import Callable

POLLING_FREQUENCY_SEC = 2


class Threshold(IntEnum):
    MAX_TEMPERATURE = 25
    MIN_TEMPERATURE = 18
    MAX_HUMIDITY = 65
    MIN_HUMIDITY = 40


THRESHOLD_RULES = {
    "temperature":
        ((operator.lt, Threshold.MIN_TEMPERATURE),
         (operator.gt, Threshold.MAX_TEMPERATURE)),
    "humidity":
        ((operator.lt, Threshold.MIN_HUMIDITY),
         (operator.gt, Threshold.MAX_HUMIDITY))
}
