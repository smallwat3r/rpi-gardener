"""Shared pytest fixtures for the test suite."""
import logging
import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

# Mock hardware-specific modules before they're imported
# These are only available on Raspberry Pi hardware
sys.modules["adafruit_dht"] = MagicMock()
sys.modules["adafruit_ssd1306"] = MagicMock()
sys.modules["aioserial"] = MagicMock()
sys.modules["board"] = MagicMock()
sys.modules["busio"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()
sys.modules["PIL.ImageDraw"] = MagicMock()
sys.modules["PIL.ImageFont"] = MagicMock()

from rpi.dht.models import Measure, Reading, State, Unit
from rpi.lib.alerts import Namespace, get_alert_tracker, reset_alert_tracker
from rpi.lib.config import set_settings


@pytest.fixture(autouse=True)
def configure_caplog(caplog):
    """Ensure caplog captures logs from the rpi namespace."""
    caplog.set_level(logging.INFO, logger="rpi")


@pytest.fixture(autouse=True)
def reset_alerts():
    """Reset the global alert tracker before each test."""
    reset_alert_tracker()
    yield
    reset_alert_tracker()


@pytest.fixture(autouse=True)
def reset_settings():
    """Reset global settings after each test to avoid cross-test pollution."""
    yield
    set_settings(None)


@pytest.fixture
def frozen_time():
    """Return a fixed datetime for deterministic tests."""
    return datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def sample_reading(frozen_time):
    """Create a valid DHT22 reading."""
    return Reading(
        temperature=Measure(22.5, Unit.CELSIUS, State.OK),
        humidity=Measure(55.0, Unit.PERCENT, State.OK),
        recording_time=frozen_time,
    )


@pytest.fixture
def mock_sensor():
    """Create a mock DHT sensor."""
    sensor = MagicMock()
    sensor.temperature = 22.0
    sensor.humidity = 50.0
    sensor.exit = MagicMock()
    return sensor


@pytest.fixture
def mock_display():
    """Create a mock display."""
    display = MagicMock()
    display.clear = MagicMock()
    display.render_reading = MagicMock()
    return display


@pytest.fixture
def dht_audit_events():
    """Capture DHT audit events published to the event bus.

    Use this fixture when testing DHT audit functionality that needs
    to verify events are published correctly.

    Returns:
        A list that will be populated with AlertEvent objects as they're published.
    """
    from rpi.lib.alerts import AlertEvent

    events: list[AlertEvent] = []

    def capture_event(event: AlertEvent) -> None:
        events.append(event)

    tracker = get_alert_tracker()
    tracker.register_callback(Namespace.DHT, capture_event)
    return events


@pytest.fixture
def pico_audit_events():
    """Capture Pico audit events published to the event bus.

    Use this fixture when testing Pico moisture auditing that needs
    to verify events are published correctly.

    Returns:
        A list that will be populated with AlertEvent objects as they're published.
    """
    from rpi.lib.alerts import AlertEvent

    events: list[AlertEvent] = []

    def capture_event(event: AlertEvent) -> None:
        events.append(event)

    tracker = get_alert_tracker()
    tracker.register_callback(Namespace.PICO, capture_event)
    return events
