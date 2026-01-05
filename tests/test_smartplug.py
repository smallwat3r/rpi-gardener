"""Tests for the smart plug integration."""

from unittest.mock import AsyncMock, patch

import pytest

from rpi.lib.alerts import Namespace
from rpi.lib.config import MeasureName, Unit
from rpi.lib.smartplug import SmartPlugController, get_smartplug_controller
from rpi.smartplug.service import _is_low_humidity_alert
from tests.conftest import make_alert_event


class TestIsLowHumidityAlert:
    """Tests for the alert filtering logic."""

    def test_returns_true_for_low_humidity_alert(self):
        """Alert fires when humidity below threshold."""
        event = make_alert_event(
            sensor_name=MeasureName.HUMIDITY,
            namespace=Namespace.DHT,
            value=35.0,
            threshold=40,
        )
        assert _is_low_humidity_alert(event) is True

    def test_returns_true_for_resolved_humidity_alert(self):
        """Resolved humidity alerts should trigger turn-off."""
        event = make_alert_event(
            sensor_name=MeasureName.HUMIDITY,
            namespace=Namespace.DHT,
            value=45.0,
            is_resolved=True,
        )
        assert _is_low_humidity_alert(event) is True

    def test_returns_false_for_high_humidity_alert(self):
        """High humidity alerts (MAX threshold) should not trigger humidifier."""
        event = make_alert_event(
            sensor_name=MeasureName.HUMIDITY,
            namespace=Namespace.DHT,
            value=75.0,
            threshold=65,  # value > threshold = MAX violation
        )
        assert _is_low_humidity_alert(event) is False

    def test_returns_false_for_temperature_alert(self):
        """Temperature alerts should not trigger humidifier."""
        event = make_alert_event(
            sensor_name=MeasureName.TEMPERATURE,
            namespace=Namespace.DHT,
            value=30.0,
            unit=Unit.CELSIUS,
            threshold=25,
        )
        assert _is_low_humidity_alert(event) is False

    def test_returns_false_for_pico_moisture_alert(self):
        """Plant moisture alerts should not trigger humidifier."""
        event = make_alert_event(
            sensor_name=1,  # Plant ID
            namespace=Namespace.PICO,
            value=20.0,
            threshold=30,
        )
        assert _is_low_humidity_alert(event) is False


class TestSmartPlugController:
    """Tests for the SmartPlugController."""

    @pytest.mark.asyncio
    async def test_turn_on_success(self):
        """Test successful turn_on operation."""
        mock_device = AsyncMock()
        mock_device.is_on = False

        controller = SmartPlugController(host="192.168.1.100")
        controller._device = mock_device

        result = await controller.turn_on()

        assert result is True
        mock_device.turn_on.assert_called_once()
        mock_device.update.assert_called()

    @pytest.mark.asyncio
    async def test_turn_off_success(self):
        """Test successful turn_off operation."""
        mock_device = AsyncMock()
        mock_device.is_on = True

        controller = SmartPlugController(host="192.168.1.100")
        controller._device = mock_device

        result = await controller.turn_off()

        assert result is True
        mock_device.turn_off.assert_called_once()
        mock_device.update.assert_called()

    @pytest.mark.asyncio
    async def test_turn_on_fails_when_not_connected(self):
        """Turn on fails gracefully when not connected."""
        controller = SmartPlugController(host="192.168.1.100")

        result = await controller.turn_on()

        assert result is False

    @pytest.mark.asyncio
    async def test_turn_off_fails_when_not_connected(self):
        """Turn off fails gracefully when not connected."""
        controller = SmartPlugController(host="192.168.1.100")

        result = await controller.turn_off()

        assert result is False

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_retry_on_network_error(self, mock_sleep):
        """Test retry logic on network errors."""
        mock_device = AsyncMock()
        mock_device.turn_on.side_effect = [OSError("Network error"), None]

        controller = SmartPlugController(host="192.168.1.100")
        controller._device = mock_device

        result = await controller.turn_on()

        assert result is True
        assert mock_device.turn_on.call_count == 2

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test device connection."""
        mock_device = AsyncMock()
        mock_device.is_on = False

        with patch(
            "rpi.lib.smartplug.Discover.discover_single",
            new_callable=AsyncMock,
            return_value=mock_device,
        ):
            controller = SmartPlugController(host="192.168.1.100")
            await controller.connect()

            assert controller.is_connected is True
            mock_device.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self):
        """Test device disconnection."""
        mock_device = AsyncMock()

        controller = SmartPlugController(host="192.168.1.100")
        controller._device = mock_device

        await controller.close()

        assert controller.is_connected is False
        mock_device.disconnect.assert_called_once()


class TestGetSmartPlugController:
    """Tests for the factory function."""

    @pytest.mark.asyncio
    async def test_returns_mock_when_mock_sensors_enabled(self):
        """Returns mock controller when MOCK_SENSORS=1."""
        from rpi.lib.config import Settings
        from rpi.lib.mock import MockSmartPlugController
        from tests.conftest import set_settings

        set_settings(
            Settings(
                smartplug_enabled=True,
                smartplug_host="192.168.1.100",
                mock_sensors=True,
            )
        )

        result = await get_smartplug_controller()

        assert result is not None
        assert isinstance(result, MockSmartPlugController)
        assert result.is_connected is True

    @pytest.mark.asyncio
    async def test_returns_none_when_disabled(self):
        """Returns None when smart plug is disabled."""
        from rpi.lib.config import Settings
        from tests.conftest import set_settings

        set_settings(Settings(smartplug_enabled=False))

        result = await get_smartplug_controller()

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_host(self):
        """Returns None when host is not configured."""
        from rpi.lib.config import Settings
        from tests.conftest import set_settings

        set_settings(Settings(smartplug_enabled=True, smartplug_host=""))

        result = await get_smartplug_controller()

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_controller_when_configured(self):
        """Returns connected controller when properly configured."""
        from rpi.lib.config import Settings
        from tests.conftest import set_settings

        set_settings(
            Settings(smartplug_enabled=True, smartplug_host="192.168.1.100")
        )

        mock_device = AsyncMock()
        mock_device.is_on = False

        with patch(
            "rpi.lib.smartplug.Discover.discover_single",
            new_callable=AsyncMock,
            return_value=mock_device,
        ):
            result = await get_smartplug_controller()

            assert result is not None
            assert result.is_connected is True

    @pytest.mark.asyncio
    async def test_returns_none_on_connection_failure(self):
        """Returns None when connection fails."""
        from rpi.lib.config import Settings
        from tests.conftest import set_settings

        set_settings(
            Settings(smartplug_enabled=True, smartplug_host="192.168.1.100")
        )

        with patch(
            "rpi.lib.smartplug.Discover.discover_single",
            new_callable=AsyncMock,
            side_effect=OSError("Connection failed"),
        ):
            result = await get_smartplug_controller()

            assert result is None
