"""Shared pytest fixtures for the test suite."""

import logging
import sys
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

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

from rpi.dht.models import Measure, Reading
from rpi.lib.alerts import AlertEvent, AlertTracker, Namespace
from rpi.lib.config import Settings, Unit
from rpi.lib.config.testing import set_settings

__all__ = ["set_settings"]


def make_alert_event(
    sensor_name: str | int = "temperature",
    value: float = 30.5,
    unit: Unit | str = Unit.CELSIUS,
    threshold: float = 25,
    recording_time: datetime | None = None,
    namespace: Namespace = Namespace.DHT,
    is_resolved: bool = False,
) -> AlertEvent:
    """Create an AlertEvent for testing."""
    if recording_time is None:
        recording_time = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
    return AlertEvent(
        namespace=namespace,
        sensor_name=sensor_name,
        value=value,
        unit=unit,  # type: ignore[arg-type]
        threshold=threshold if not is_resolved else None,
        recording_time=recording_time,
        is_resolved=is_resolved,
    )


@pytest.fixture(autouse=True)
def configure_caplog(caplog):
    """Ensure caplog captures logs from the rpi namespace."""
    caplog.set_level(logging.INFO, logger="rpi")


@pytest.fixture
def alert_tracker():
    """Provide a fresh AlertTracker for each test.

    Uses confirmation_count=1 so tests see immediate state transitions.
    Production uses the configured default (typically 3).
    """
    return AlertTracker(confirmation_count=1)


@pytest.fixture(autouse=True)
def reset_settings():
    """Reset global settings after each test to avoid cross-test pollution."""
    from rpi.lib.db.settings import _invalidate_settings_cache

    _invalidate_settings_cache()
    yield
    set_settings(None)
    _invalidate_settings_cache()


@pytest.fixture(autouse=True)
async def test_db(tmp_path):
    """Use a temporary SQLite database for tests.

    This creates a fresh database with the full schema for each test,
    providing isolation while allowing real database operations.
    The database file is automatically cleaned up after each test.
    """
    import sqlite3
    from pathlib import Path

    from rpi.lib.db import close_db

    # Create a unique database file for this test
    db_file = tmp_path / "test.sqlite3"

    # Override settings to use the temp database
    # Use a fake serial port to avoid RuntimeError from pico auto-detection
    test_settings = Settings(db_path=str(db_file), pico_serial_port="/dev/null")
    set_settings(test_settings)

    # Initialize the schema using sync sqlite3 (simpler for setup)
    sql_dir = Path(__file__).parent.parent / "rpi" / "lib" / "sql"
    conn = sqlite3.connect(str(db_file))
    conn.executescript((sql_dir / "init_reading_table.sql").read_text())
    conn.executescript((sql_dir / "init_pico_reading_table.sql").read_text())
    conn.executescript((sql_dir / "init_settings_table.sql").read_text())
    conn.executescript((sql_dir / "init_admin_table.sql").read_text())
    conn.close()

    yield
    # Clean up database connection pool
    await close_db()


@pytest.fixture
def frozen_time():
    """Return a fixed datetime for deterministic tests."""
    return datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def sample_reading(frozen_time):
    """Create a valid DHT22 reading."""
    return Reading(
        temperature=Measure(22.5, Unit.CELSIUS),
        humidity=Measure(55.0, Unit.PERCENT),
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
async def dht_audit_events(alert_tracker):
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

    await alert_tracker.register_callback(Namespace.DHT, capture_event)
    return events


@pytest.fixture
async def pico_audit_events(alert_tracker):
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

    await alert_tracker.register_callback(Namespace.PICO, capture_event)
    return events


@pytest.fixture
def mock_publisher():
    """Create a mock event publisher for polling services."""
    publisher = MagicMock()
    publisher.connect = MagicMock()
    publisher.publish = MagicMock()
    publisher.close = MagicMock()
    return publisher


@pytest.fixture
def mock_source():
    """Create a mock data source for Pico polling service."""
    source = MagicMock()
    source.readline = AsyncMock()
    source.close = MagicMock()
    return source
