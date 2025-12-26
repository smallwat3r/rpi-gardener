"""Domain models for DHT22 sensor readings."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, StrEnum, auto


class Unit(StrEnum):
    CELSIUS = "c"
    PERCENT = "%"


class State(Enum):
    OK = auto()
    IN_ALERT = auto()


@dataclass(slots=True)
class Measure:
    value: float
    unit: Unit
    state: State = State.OK

    def __str__(self) -> str:
        return f"{self.value}{self.unit}"


@dataclass(slots=True)
class Reading:
    temperature: Measure
    humidity: Measure
    recording_time: datetime
