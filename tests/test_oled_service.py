"""Tests for the OLED display service."""

import pytest

from rpi.lib.mock import MockOLEDDisplay


class TestMockOLEDDisplay:
    """Tests for the MockOLEDDisplay class."""

    def test_init(self, caplog):
        display = MockOLEDDisplay()
        assert display is not None
        assert "initialized" in caplog.text.lower()

    def test_render(self, caplog):
        display = MockOLEDDisplay()
        display.render(22.5, 55.0)
        assert "22.5" in caplog.text
        assert "55.0" in caplog.text

    def test_render_various_values(self, caplog):
        display = MockOLEDDisplay()

        display.render(0.0, 0.0)
        assert "0.0" in caplog.text

        display.render(-5.5, 100.0)
        assert "-5.5" in caplog.text
        assert "100.0" in caplog.text

    def test_clear(self):
        display = MockOLEDDisplay()
        display.clear()  # Should not raise

    def test_close(self, caplog):
        display = MockOLEDDisplay()
        display.close()
        assert "closed" in caplog.text.lower()

    def test_context_manager(self, caplog):
        with MockOLEDDisplay() as display:
            display.render(20.0, 50.0)
            assert "20.0" in caplog.text
        assert "closed" in caplog.text.lower()


class TestOLEDServiceCreateDisplay:
    """Tests for the _create_display factory function."""

    def test_returns_mock_when_mock_sensors_enabled(self):
        from rpi.lib.config import Settings
        from rpi.oled.service import _create_display
        from tests.conftest import set_settings

        set_settings(Settings(mock_sensors=True))
        display = _create_display()
        assert isinstance(display, MockOLEDDisplay)

    @pytest.mark.skipif(
        True, reason="Requires hardware - only run on Raspberry Pi"
    )
    def test_returns_real_display_when_mock_disabled(self):
        from rpi.lib.config import Settings
        from rpi.oled.display import Display
        from rpi.oled.service import _create_display
        from tests.conftest import set_settings

        set_settings(Settings(mock_sensors=False))
        display = _create_display()
        assert isinstance(display, Display)
