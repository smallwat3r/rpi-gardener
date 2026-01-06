"""Mock sensor data generators for development.

Provides mock implementations of sensor interfaces that generate
realistic data without requiring hardware. Used by polling/reader
services when MOCK_SENSORS=1 is set.

The random_walk function is shared with scripts/seed_data.py for
consistent data patterns between seeded and live mock data.
"""

import random
from typing import Self

from rpi.lib.config import PlantId


def random_walk(
    current: float, drift: float, min_val: float, max_val: float
) -> float:
    """Generate next value using random walk with bounds.

    Shared algorithm used by both mock sensors and seed_data.py script
    to ensure consistent data patterns.

    Args:
        current: Current value to drift from.
        drift: Standard deviation for gaussian noise.
        min_val: Lower bound for the result.
        max_val: Upper bound for the result.

    Returns:
        New value within [min_val, max_val].
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
        self._temperature = random_walk(
            self._temperature, drift=0.15, min_val=15.0, max_val=30.0
        )
        return round(self._temperature, 1)

    @property
    def humidity(self) -> float:
        self._humidity = random_walk(
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
        self._moisture[plant_id] = random_walk(
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


class MockOLEDDisplay:
    """Mock OLED display that logs output for development."""

    def __init__(self) -> None:
        from rpi.logging import get_logger

        self._logger = get_logger("lib.mock.oled")
        self._logger.info("Mock OLED display initialized")

    def clear(self) -> None:
        """Clear the display."""
        self._logger.debug("OLED cleared")

    def render(self, temperature: float, humidity: float) -> None:
        """Render temperature and humidity."""
        self._logger.info("OLED: %.1f C | %.1f %%", temperature, humidity)

    def close(self) -> None:
        """Close the display."""
        self._logger.info("Mock OLED display closed")

    def __enter__(self) -> Self:
        """Enter context manager."""
        return self

    def __exit__(self, *_: object) -> None:
        """Exit context manager."""
        self.close()


class MockLCDDisplay:
    """Mock LCD 1602A display that logs output for development."""

    def __init__(self) -> None:
        from rpi.logging import get_logger

        self._logger = get_logger("lib.mock.lcd")
        self._alerts: list[str] = []
        self._logger.info("Mock LCD display initialized")

    def clear(self) -> None:
        """Clear the display."""
        self._alerts = []
        self._logger.debug("LCD cleared")

    def show_ok(self) -> None:
        """Display 'all ok' status."""
        self._alerts = []
        self._logger.info("LCD: STATUS - All OK")

    def show_alerts(self, alerts: list[str]) -> None:
        """Display alerts."""
        self._alerts = alerts
        self._logger.info(
            "LCD: ALERTS: %d - %s", len(alerts), " | ".join(alerts)
        )

    def scroll_step(self) -> None:
        """Advance scroll position (no-op for mock)."""

    def close(self) -> None:
        """Close the display."""
        self._logger.info("Mock LCD display closed")

    def __enter__(self) -> Self:
        """Enter context manager."""
        return self

    def __exit__(self, *_: object) -> None:
        """Exit context manager."""
        self.close()


class MockSmartPlugController:
    """Mock smart plug controller that logs actions instead of controlling hardware."""

    def __init__(self, host: str, *, turn_off_on_close: bool = False) -> None:
        self._host = host
        self._is_on = False
        self._turn_off_on_close = turn_off_on_close

    @property
    def turn_off_on_close(self) -> bool:
        """Whether to turn off the plug when closing."""
        return self._turn_off_on_close

    async def connect(self) -> None:
        """Simulate connection."""
        from rpi.logging import get_logger

        logger = get_logger("lib.smartplug")
        logger.info("Mock smart plug connected at %s", self._host)

    async def turn_on(self) -> bool:
        """Simulate turning on."""
        from rpi.logging import get_logger

        logger = get_logger("lib.smartplug")
        self._is_on = True
        logger.info("Mock smart plug turned ON")
        return True

    async def turn_off(self) -> bool:
        """Simulate turning off."""
        from rpi.logging import get_logger

        logger = get_logger("lib.smartplug")
        self._is_on = False
        logger.info("Mock smart plug turned OFF")
        return True

    @property
    def is_connected(self) -> bool:
        """Always connected in mock mode."""
        return True

    async def close(self) -> None:
        """Simulate disconnection."""
        from rpi.logging import get_logger

        logger = get_logger("lib.smartplug")
        if self._turn_off_on_close:
            logger.info(
                "Turning off mock smart plug before disconnect (safety)"
            )
            await self.turn_off()
        logger.info("Mock smart plug disconnected")

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        """Async context manager exit."""
        await self.close()
