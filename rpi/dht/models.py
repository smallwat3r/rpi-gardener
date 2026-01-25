"""Domain models for DHT22 sensor readings."""

from dataclasses import dataclass
from datetime import datetime

from rpi.lib.config import Unit


@dataclass(slots=True)
class Measure:
    value: float
    unit: Unit

    def __str__(self) -> str:
        return f"{self.value}{self.unit}"


@dataclass(slots=True)
class Reading:
    temperature: Measure
    humidity: Measure
    recording_time: datetime
