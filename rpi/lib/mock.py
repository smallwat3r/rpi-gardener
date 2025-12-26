"""Mock sensor data generators for development.

Provides mock implementations of sensor interfaces that generate
realistic data without requiring hardware. Used by polling/reader
services when MOCK_SENSORS=1 is set.

Uses the same random walk algorithm as scripts/seed_data.py for
consistent data patterns between seeded and live mock data.
"""

import random

from rpi.lib.config import PlantId


def _random_walk(
    current: float, drift: float, min_val: float, max_val: float
) -> float:
    """Generate next value using random walk with bounds.

    Same algorithm as scripts/seed_data.py for consistent data patterns.
    """
    change = random.gauss(0, drift)
    new_val = current + change
    return max(min_val, min(max_val, new_val))


class MockDHTSensor:
    """Mock DHT22 sensor that generates realistic readings.

    Uses same parameters as seed_data.py:
    - Temperature: drift=0.15, bounds 15-30
    - Humidity: drift=0.3, bounds 30-70
    """

    def __init__(self) -> None:
        self._temperature = random.uniform(20.0, 23.0)
        self._humidity = random.uniform(45.0, 55.0)

    @property
    def temperature(self) -> float:
        self._temperature = _random_walk(
            self._temperature, drift=0.15, min_val=15.0, max_val=30.0
        )
        return round(self._temperature, 1)

    @property
    def humidity(self) -> float:
        self._humidity = _random_walk(
            self._humidity, drift=0.3, min_val=30.0, max_val=70.0
        )
        return round(self._humidity, 1)

    def exit(self) -> None:
        """No-op for mock sensor."""


class MockPicoDataSource:
    """Mock Pico data source that generates realistic moisture readings.

    Uses same parameters as seed_data.py:
    - Moisture: drift=0.5, bounds 10-90
    - Initial values: random 40-70 per plant
    """

    def __init__(self, frequency_sec: float = 2.0) -> None:
        self._frequency_sec = frequency_sec
        self._moisture = {
            plant_id: random.uniform(40.0, 70.0) for plant_id in PlantId
        }

    def _generate_moisture(self, plant_id: PlantId) -> float:
        """Generate a realistic moisture reading for a plant."""
        self._moisture[plant_id] = _random_walk(
            self._moisture[plant_id], drift=0.5, min_val=10.0, max_val=90.0
        )
        return round(self._moisture[plant_id], 1)

    async def readline(self) -> str:
        """Generate a line of mock Pico JSON data."""
        import asyncio
        import json

        await asyncio.sleep(self._frequency_sec)

        data = {
            f"plant-{plant_id.value}": self._generate_moisture(plant_id)
            for plant_id in PlantId
        }
        return json.dumps(data)

    def close(self) -> None:
        """No-op for mock data source."""


class MockDisplay:
    """Mock OLED display that does nothing (for development without hardware)."""

    def clear(self) -> None:
        """No-op."""

    def render_reading(self, reading: object) -> None:
        """No-op."""
