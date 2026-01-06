"""TP-Link Kasa smart plug control module.

Provides async interface to control Kasa smart plugs with retry logic
and proper error handling.
"""

from typing import Protocol, Self

from kasa import Device, Discover

from rpi.lib.config import get_settings
from rpi.lib.retry import with_retry
from rpi.logging import get_logger

logger = get_logger("lib.smartplug")


class SmartPlugProtocol(Protocol):
    """Protocol defining the smart plug controller interface."""

    @property
    def is_connected(self) -> bool: ...
    @property
    def turn_off_on_close(self) -> bool: ...
    async def connect(self) -> None: ...
    async def turn_on(self) -> bool: ...
    async def turn_off(self) -> bool: ...
    async def close(self) -> None: ...
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *_: object) -> None: ...


class SmartPlugController:
    """Controller for TP-Link Kasa smart plug devices."""

    def __init__(self, host: str, *, turn_off_on_close: bool = False) -> None:
        self._host = host
        self._device: Device | None = None
        self._turn_off_on_close = turn_off_on_close

    @property
    def turn_off_on_close(self) -> bool:
        """Whether to turn off the plug when closing the connection."""
        return self._turn_off_on_close

    async def connect(self) -> None:
        """Connect to the smart plug device."""

        async def do_connect() -> None:
            self._device = await Discover.discover_single(self._host)
            if self._device is None:
                raise ConnectionError(f"Device not found at {self._host}")
            await self._device.update()

        success = await with_retry(
            do_connect,
            name="SmartPlug connect",
            logger=logger,
            max_retries=3,
            initial_backoff_sec=2.0,
            retryable_exceptions=(OSError, TimeoutError, ConnectionError),
        )

        if not success:
            raise ConnectionError(
                f"Failed to connect to device at {self._host}"
            )

        logger.info(
            "Connected to smart plug at %s (is_on=%s)",
            self._host,
            self._device.is_on,  # type: ignore[union-attr]
        )

    async def turn_on(self) -> bool:
        """Turn on the smart plug. Returns True if successful."""
        if self._device is None:
            logger.warning("Cannot turn on: plug not connected")
            return False

        async def do_turn_on() -> None:
            assert self._device is not None
            await self._device.turn_on()
            await self._device.update()

        success = await with_retry(
            do_turn_on,
            name="SmartPlug turn_on",
            logger=logger,
            max_retries=3,
            initial_backoff_sec=2.0,
            retryable_exceptions=(OSError, TimeoutError),
        )

        if success:
            logger.info("Smart plug turned ON")
        return success

    async def turn_off(self) -> bool:
        """Turn off the smart plug. Returns True if successful."""
        if self._device is None:
            logger.warning("Cannot turn off: plug not connected")
            return False

        async def do_turn_off() -> None:
            assert self._device is not None
            await self._device.turn_off()
            await self._device.update()

        success = await with_retry(
            do_turn_off,
            name="SmartPlug turn_off",
            logger=logger,
            max_retries=3,
            initial_backoff_sec=2.0,
            retryable_exceptions=(OSError, TimeoutError),
        )

        if success:
            logger.info("Smart plug turned OFF")
        return success

    @property
    def is_connected(self) -> bool:
        """Check if connected to the plug."""
        return self._device is not None

    async def close(self) -> None:
        """Close the connection to the smart plug.

        If turn_off_on_close was set, turns off the plug before disconnecting.
        """
        if self._device is not None:
            if self._turn_off_on_close:
                logger.info(
                    "Turning off smart plug before disconnect (safety)"
                )
                await self.turn_off()
            await self._device.disconnect()
            self._device = None
            logger.info("Disconnected from smart plug")

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        """Async context manager exit."""
        await self.close()


def create_smartplug_controller(
    host: str,
    *,
    turn_off_on_close: bool = False,
) -> SmartPlugProtocol:
    """Create a smart plug controller for the given host.

    Args:
        host: IP address or hostname of the smart plug.
        turn_off_on_close: If True, turn off the plug when closing.
            Use this for safety-critical devices like humidifiers.

    Use as context manager: async with create_smartplug_controller(host) as ctrl:
    """
    settings = get_settings()

    if settings.mock_sensors:
        from rpi.lib.mock import MockSmartPlugController

        logger.info("Using mock smart plug controller for %s", host)
        return MockSmartPlugController(
            host=host, turn_off_on_close=turn_off_on_close
        )

    return SmartPlugController(host=host, turn_off_on_close=turn_off_on_close)
