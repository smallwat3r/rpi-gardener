"""Shared pytest fixtures for the test suite."""
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
from rpi.lib.alerts import reset_alert_tracker
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


