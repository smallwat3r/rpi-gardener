"""OLED service that displays temperature and humidity readings.

Subscribes to the event bus DHT_READING topic and renders the latest
readings on an SSD1306 OLED display.
"""

import asyncio
import signal
from contextlib import suppress

from rpi.lib.config import get_settings
from rpi.lib.eventbus import EventSubscriber, Topic
from rpi.logging import configure, get_logger
from rpi.oled.display import DisplayProtocol

logger = get_logger("oled.service")


def _create_display() -> DisplayProtocol:
    """Create display based on configuration."""
    if get_settings().mock_sensors:
        from rpi.lib.mock import MockOLEDDisplay

        logger.info("Using mock OLED display")
        return MockOLEDDisplay()

    from rpi.oled.display import Display

    return Display()


async def run() -> None:
    """Run the OLED service."""
    with _create_display() as display:
        display.clear()

        async with EventSubscriber(topics=[Topic.DHT_READING]) as subscriber:
            logger.info("OLED service started")
            async for _topic, data in subscriber.receive():
                try:
                    temperature = data.get("temperature")
                    humidity = data.get("humidity")
                    if temperature is not None and humidity is not None:
                        display.render(temperature, humidity)
                except (KeyError, ValueError, TypeError):
                    logger.exception("Failed to parse DHT reading event")

    logger.info("OLED service stopped")


def main() -> None:
    """Entry point for the OLED service."""
    configure()

    if not get_settings().oled.enabled:
        logger.info("OLED service is disabled, exiting")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, loop.stop)

    with suppress(KeyboardInterrupt):
        loop.run_until_complete(run())
    loop.close()


if __name__ == "__main__":
    main()
