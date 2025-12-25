"""Mock sensor data generators for development.

Provides mock implementations of sensor interfaces that generate
realistic data without requiring hardware. Used by polling/reader
services when MOCK_SENSORS=1 is set.
"""
import math
import random
import time

from rpi.lib.config import PlantId

# Seed for reproducible "randomness" that still varies over time
_start_time = time.time()


def _smooth_noise(t: float, seed: float = 0.0) -> float:
    """Generate smooth noise value between -1 and 1.

    Uses multiple sine waves at different frequencies to create
    natural-looking variations (poor man's Perlin noise).
    """
    return (
        math.sin(t * 0.1 + seed) * 0.5
        + math.sin(t * 0.23 + seed * 2) * 0.3
        + math.sin(t * 0.07 + seed * 3) * 0.2
    )


def _get_time_factor() -> float:
    """Get time factor for noise generation (changes slowly over time)."""
    return time.time() - _start_time


class MockDHTSensor:
    """Mock DHT22 sensor that generates realistic readings.

    Temperature varies around 21C (typical indoor temp).
    Humidity varies around 52% (typical indoor humidity).
    Both have smooth, correlated variations.
    """

    @property
    def temperature(self) -> float:
        t = _get_time_factor()
        base_temp = 21.0
        temp_variation = _smooth_noise(t, seed=1.0) * 3.0
        temp_jitter = random.uniform(-0.1, 0.1)
        return round(base_temp + temp_variation + temp_jitter, 1)

    @property
    def humidity(self) -> float:
        t = _get_time_factor()
        base_humidity = 52.0
        temp_variation = _smooth_noise(t, seed=1.0) * 3.0
        humidity_variation = _smooth_noise(t, seed=2.0) * 12.0 - temp_variation * 1.5
        humidity_jitter = random.uniform(-0.5, 0.5)
        return round(
            max(30.0, min(80.0, base_humidity + humidity_variation + humidity_jitter)),
            1,
        )

    def exit(self) -> None:
        """No-op for mock sensor."""


class MockPicoDataSource:
    """Mock Pico data source that generates realistic moisture readings.

    Each plant has different base moisture levels and variation patterns
    to simulate real plant conditions.
    """

    def __init__(self, frequency_sec: float = 2.0) -> None:
        self._frequency_sec = frequency_sec
        self._plant_configs = {
            PlantId.PLANT_1: {"base": 55.0, "variation": 15.0, "seed": 20.0},
            PlantId.PLANT_2: {"base": 42.0, "variation": 12.0, "seed": 21.0},
            PlantId.PLANT_3: {"base": 35.0, "variation": 10.0, "seed": 22.0},
        }

    def _generate_moisture(self, plant_id: PlantId) -> float:
        """Generate a realistic moisture reading for a plant."""
        t = _get_time_factor()
        config = self._plant_configs[plant_id]
        moisture_variation = _smooth_noise(t, seed=config["seed"]) * config["variation"]
        moisture_jitter = random.uniform(-1.0, 1.0)
        return round(
            max(5.0, min(95.0, config["base"] + moisture_variation + moisture_jitter)),
            1,
        )

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

    def render_reading(self, reading) -> None:
        """No-op."""
