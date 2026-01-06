"""Tests for the LCD display service."""

from unittest.mock import MagicMock

import pytest

from rpi.lcd.service import AlertManager, _format_alert, _make_alert_key
from rpi.lib.alerts import Namespace
from rpi.lib.config import MeasureName
from rpi.lib.mock import MockLCDDisplay
from tests.conftest import make_alert_event


class TestAlertFormatting:
    """Tests for alert key and message formatting."""

    def test_make_alert_key_dht(self, frozen_time):
        event = make_alert_event(
            sensor_name="temperature",
            value=30.0,
            unit="c",
            threshold=25,
            recording_time=frozen_time,
            namespace=Namespace.DHT,
        )
        assert _make_alert_key(event) == "dht:temperature"

    def test_make_alert_key_pico(self, frozen_time):
        event = make_alert_event(
            sensor_name="1",
            value=20.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
            namespace=Namespace.PICO,
        )
        assert _make_alert_key(event) == "pico:1"

    def test_format_alert_pico_dry(self, frozen_time):
        event = make_alert_event(
            sensor_name="2",
            value=20.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
            namespace=Namespace.PICO,
        )
        assert _format_alert(event) == "P2 dry"

    def test_format_alert_temp_high(self, frozen_time):
        event = make_alert_event(
            sensor_name=MeasureName.TEMPERATURE,
            value=30.0,
            unit="c",
            threshold=25,
            recording_time=frozen_time,
            namespace=Namespace.DHT,
        )
        assert _format_alert(event) == "Temp high"

    def test_format_alert_temp_low(self, frozen_time):
        event = make_alert_event(
            sensor_name=MeasureName.TEMPERATURE,
            value=15.0,
            unit="c",
            threshold=18,
            recording_time=frozen_time,
            namespace=Namespace.DHT,
        )
        assert _format_alert(event) == "Temp low"

    def test_format_alert_humidity_high(self, frozen_time):
        event = make_alert_event(
            sensor_name=MeasureName.HUMIDITY,
            value=75.0,
            unit="%",
            threshold=65,
            recording_time=frozen_time,
            namespace=Namespace.DHT,
        )
        assert _format_alert(event) == "Humid high"

    def test_format_alert_humidity_low(self, frozen_time):
        event = make_alert_event(
            sensor_name=MeasureName.HUMIDITY,
            value=35.0,
            unit="%",
            threshold=40,
            recording_time=frozen_time,
            namespace=Namespace.DHT,
        )
        assert _format_alert(event) == "Humid low"


class TestAlertManager:
    """Tests for the AlertManager class."""

    @pytest.fixture
    def mock_display(self):
        display = MagicMock()
        display.show_ok = MagicMock()
        display.show_alerts = MagicMock()
        return display

    @pytest.fixture
    def manager(self, mock_display):
        return AlertManager(mock_display)

    def test_initial_state_no_alerts(self, manager):
        assert manager.has_alerts() is False

    def test_handle_new_alert(self, manager, mock_display, frozen_time):
        event = make_alert_event(
            sensor_name=MeasureName.TEMPERATURE,
            value=30.0,
            unit="c",
            threshold=25,
            recording_time=frozen_time,
            namespace=Namespace.DHT,
        )

        manager.handle_event(event)

        assert manager.has_alerts() is True
        mock_display.show_alerts.assert_called_once_with(["Temp high"])

    def test_handle_resolved_alert(self, manager, mock_display, frozen_time):
        # First trigger an alert
        event = make_alert_event(
            sensor_name=MeasureName.TEMPERATURE,
            value=30.0,
            unit="c",
            threshold=25,
            recording_time=frozen_time,
            namespace=Namespace.DHT,
        )
        manager.handle_event(event)

        # Then resolve it
        resolved = make_alert_event(
            sensor_name=MeasureName.TEMPERATURE,
            value=22.0,
            unit="c",
            recording_time=frozen_time,
            namespace=Namespace.DHT,
            is_resolved=True,
        )
        manager.handle_event(resolved)

        assert manager.has_alerts() is False
        mock_display.show_ok.assert_called()

    def test_multiple_alerts(self, manager, mock_display, frozen_time):
        # Trigger temperature alert
        temp_event = make_alert_event(
            sensor_name=MeasureName.TEMPERATURE,
            value=30.0,
            unit="c",
            threshold=25,
            recording_time=frozen_time,
            namespace=Namespace.DHT,
        )
        manager.handle_event(temp_event)

        # Trigger humidity alert
        humid_event = make_alert_event(
            sensor_name=MeasureName.HUMIDITY,
            value=75.0,
            unit="%",
            threshold=65,
            recording_time=frozen_time,
            namespace=Namespace.DHT,
        )
        manager.handle_event(humid_event)

        assert manager.has_alerts() is True
        # Should show both alerts
        call_args = mock_display.show_alerts.call_args[0][0]
        assert len(call_args) == 2
        assert "Temp high" in call_args
        assert "Humid high" in call_args

    def test_resolve_nonexistent_alert(
        self, manager, mock_display, frozen_time
    ):
        """Resolving an alert that doesn't exist should be a no-op."""
        resolved = make_alert_event(
            sensor_name=MeasureName.TEMPERATURE,
            value=22.0,
            unit="c",
            recording_time=frozen_time,
            namespace=Namespace.DHT,
            is_resolved=True,
        )
        manager.handle_event(resolved)

        assert manager.has_alerts() is False
        mock_display.show_ok.assert_called()


class TestMockLCDDisplay:
    """Tests for the MockLCDDisplay class."""

    def test_init(self):
        display = MockLCDDisplay()
        assert display is not None

    def test_show_ok(self, caplog):
        display = MockLCDDisplay()
        display.show_ok()
        assert "All OK" in caplog.text

    def test_show_alerts(self, caplog):
        display = MockLCDDisplay()
        display.show_alerts(["Temp high", "P1 dry"])
        assert "ALERTS: 2" in caplog.text
        assert "Temp high" in caplog.text
        assert "P1 dry" in caplog.text

    def test_clear(self):
        display = MockLCDDisplay()
        display.clear()  # Should not raise

    def test_scroll_step(self):
        display = MockLCDDisplay()
        display.scroll_step()  # Should not raise (no-op)

    def test_close(self, caplog):
        display = MockLCDDisplay()
        display.close()
        assert "closed" in caplog.text.lower()

    def test_context_manager(self, caplog):
        with MockLCDDisplay() as display:
            display.show_alerts(["Test alert"])
            assert "Test alert" in caplog.text
        assert "closed" in caplog.text.lower()


class TestLCDServiceCreateDisplay:
    """Tests for the _create_display factory function."""

    def test_returns_mock_when_mock_sensors_enabled(self):
        from rpi.lcd.service import _create_display
        from rpi.lib.config import Settings
        from tests.conftest import set_settings

        set_settings(Settings(mock_sensors=True))
        display = _create_display()
        assert isinstance(display, MockLCDDisplay)

    @pytest.mark.skipif(
        True, reason="Requires hardware - only run on Raspberry Pi"
    )
    def test_returns_real_display_when_mock_disabled(self):
        from rpi.lcd.display import Display
        from rpi.lcd.service import _create_display
        from rpi.lib.config import Settings
        from tests.conftest import set_settings

        set_settings(Settings(mock_sensors=False))
        display = _create_display()
        assert isinstance(display, Display)
