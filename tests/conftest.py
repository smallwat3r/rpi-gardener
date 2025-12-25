"""Shared pytest fixtures for the test suite."""
import asyncio
import logging
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

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
    return datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def mock_utcnow(frozen_time):
    """Patch utcnow() to return a fixed time."""
    with patch("rpi.lib.utils.utcnow", return_value=frozen_time) as mock:
        yield mock


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
def dht_audit_queue():
    """Initialize DHT audit queue and register callback.

    Use this fixture when testing DHT audit functionality that needs
    the event queue and callback registration.
    """
    from rpi.dht import audit
    from rpi.dht.audit import _enqueue_event

    audit._queue = asyncio.Queue()
    tracker = get_alert_tracker()
    tracker.register_callback(Namespace.DHT, _enqueue_event)
    return audit._queue


@pytest.fixture
def pico_alerts_registered():
    """Register Pico alerts callback.

    Use this fixture when testing Pico moisture auditing that needs
    the alert callback registration.
    """
    from rpi.pico.reader import _register_pico_alerts

    _register_pico_alerts()
