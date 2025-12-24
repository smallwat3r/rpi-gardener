"""Shared pytest fixtures for the test suite."""
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Mock hardware-specific modules before they're imported
# These are only available on Raspberry Pi hardware
sys.modules["adafruit_dht"] = MagicMock()
sys.modules["adafruit_ssd1306"] = MagicMock()
sys.modules["board"] = MagicMock()
sys.modules["busio"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()
sys.modules["PIL.ImageDraw"] = MagicMock()
sys.modules["PIL.ImageFont"] = MagicMock()

from rpi.dht.models import Measure, Reading, State, Unit


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
def mock_db():
    """Mock database context manager."""
    db_mock = MagicMock()
    db_mock.commit = MagicMock()

    cm_mock = MagicMock()
    cm_mock.__enter__ = MagicMock(return_value=db_mock)
    cm_mock.__exit__ = MagicMock(return_value=False)

    with patch("rpi.lib.config.db_with_config", return_value=cm_mock):
        yield db_mock


@pytest.fixture
def mock_notifier():
    """Mock notifier for testing alerts."""
    notifier = MagicMock()
    notifier.send = MagicMock()
    with patch("rpi.lib.notifications.get_notifier", return_value=notifier):
        yield notifier


@pytest.fixture
def mock_display():
    """Mock OLED display."""
    with patch("rpi.dht.display.display") as mock:
        mock.render_reading = MagicMock()
        mock.clear = MagicMock()
        yield mock
