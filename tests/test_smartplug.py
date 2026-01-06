"""Tests for the smart plug integration."""

from unittest.mock import AsyncMock, patch

import pytest

from rpi.humidifier.service import _is_low_humidity_alert
from rpi.lib.alerts import Namespace
from rpi.lib.config import MeasureName, Unit
from rpi.lib.smartplug import SmartPlugController, create_smartplug_controller
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

    @pytest.mark.asyncio
    async def test_close_turns_off_when_turn_off_on_close_enabled(self):
        """Close turns off the plug when turn_off_on_close=True."""
        mock_device = AsyncMock()

        controller = SmartPlugController(
            host="192.168.1.100", turn_off_on_close=True
        )
        controller._device = mock_device

        await controller.close()

        mock_device.turn_off.assert_called_once()
        mock_device.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_does_not_turn_off_by_default(self):
        """Close does not turn off the plug by default."""
        mock_device = AsyncMock()

        controller = SmartPlugController(host="192.168.1.100")
        controller._device = mock_device

        await controller.close()

        mock_device.turn_off.assert_not_called()
        mock_device.disconnect.assert_called_once()

    def test_turn_off_on_close_property(self):
        """Property returns the configured value."""
        controller_off = SmartPlugController(
            host="192.168.1.100", turn_off_on_close=False
        )
        controller_on = SmartPlugController(
            host="192.168.1.100", turn_off_on_close=True
        )

        assert controller_off.turn_off_on_close is False
        assert controller_on.turn_off_on_close is True


class TestCreateSmartPlugController:
    """Tests for the factory function."""

    @pytest.mark.asyncio
    async def test_returns_mock_when_mock_sensors_enabled(self):
        """Returns mock controller when MOCK_SENSORS=1."""
        from rpi.lib.config import Settings
        from rpi.lib.mock import MockSmartPlugController
        from tests.conftest import set_settings

        set_settings(Settings(mock_sensors=True))

        result = create_smartplug_controller("192.168.1.100")

        assert isinstance(result, MockSmartPlugController)
        async with result:
            assert result.is_connected is True

    @pytest.mark.asyncio
    async def test_returns_real_controller(self):
        """Returns real controller when mock_sensors is disabled."""
        from rpi.lib.config import Settings
        from tests.conftest import set_settings

        set_settings(Settings(mock_sensors=False))

        mock_device = AsyncMock()
        mock_device.is_on = False

        with patch(
            "rpi.lib.smartplug.Discover.discover_single",
            new_callable=AsyncMock,
            return_value=mock_device,
        ):
            result = create_smartplug_controller("192.168.1.100")

            assert isinstance(result, SmartPlugController)
            async with result:
                assert result.is_connected is True

    @pytest.mark.asyncio
    async def test_connection_failure_raises_in_context(self):
        """Connection failure is raised when entering context."""
        from rpi.lib.config import Settings
        from tests.conftest import set_settings

        set_settings(Settings(mock_sensors=False))

        with (
            patch(
                "rpi.lib.smartplug.Discover.discover_single",
                new_callable=AsyncMock,
                side_effect=OSError("Connection failed"),
            ),
            patch("rpi.lib.retry.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = create_smartplug_controller("192.168.1.100")

            with pytest.raises(ConnectionError, match="Failed to connect"):
                async with result:
                    pass

    def test_passes_turn_off_on_close_to_controller(self):
        """Factory passes turn_off_on_close parameter to controller."""
        from rpi.lib.config import Settings
        from tests.conftest import set_settings

        set_settings(Settings(mock_sensors=False))

        controller = create_smartplug_controller(
            "192.168.1.100", turn_off_on_close=True
        )

        assert controller.turn_off_on_close is True

    def test_passes_turn_off_on_close_to_mock_controller(self):
        """Factory passes turn_off_on_close parameter to mock controller."""
        from rpi.lib.config import Settings
        from tests.conftest import set_settings

        set_settings(Settings(mock_sensors=True))

        controller = create_smartplug_controller(
            "192.168.1.100", turn_off_on_close=True
        )

        assert controller.turn_off_on_close is True
