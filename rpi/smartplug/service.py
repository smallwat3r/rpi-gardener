"""Smart plug service that controls a humidifier based on humidity alerts.

Subscribes to the event bus ALERT topic and controls a TP-Link Kasa
smart plug to turn a humidifier on/off based on humidity levels.

- Humidifier turns ON when humidity is too LOW (alert triggered)
- Humidifier turns OFF when humidity recovers (alert resolved)
"""

import asyncio
import signal
from contextlib import suppress

from rpi.lib.alerts import AlertEvent, Namespace
from rpi.lib.config import MeasureName, get_settings
from rpi.lib.eventbus import EventSubscriber, Topic
from rpi.lib.smartplug import SmartPlugProtocol, get_smartplug_controller
from rpi.logging import configure, get_logger

logger = get_logger("smartplug.service")


def _is_low_humidity_alert(event: AlertEvent) -> bool:
    """Check if this is a low humidity alert from DHT sensor."""
    is_humidity = (
        event.namespace == Namespace.DHT
        and event.sensor_name == MeasureName.HUMIDITY
    )
    is_low = event.threshold is not None and event.value < event.threshold
    return is_humidity and (event.is_resolved or is_low)


async def _handle_humidity_event(
    event: AlertEvent, controller: SmartPlugProtocol
) -> None:
    """Handle a humidity alert by controlling the smart plug."""
    if event.is_resolved:
        logger.info(
            "Humidity recovered to %.1f%% - turning OFF humidifier",
            event.value,
        )
        await controller.turn_off()
    else:
        logger.info(
            "Humidity too low at %.1f%% (threshold: %.0f%%) - "
            "turning ON humidifier",
            event.value,
            event.threshold,
        )
        await controller.turn_on()


async def run() -> None:
    """Run the smart plug service."""
    controller = await get_smartplug_controller()

    if controller is None:
        logger.warning("Smart plug controller not available, service exiting")
        return

    try:
        async with EventSubscriber(topics=[Topic.ALERT]) as subscriber:
            logger.info("Smart plug service started")
            async for _topic, data in subscriber.receive():
                try:
                    event = AlertEvent.from_dict(data)

                    if not _is_low_humidity_alert(event):
                        continue

                    await _handle_humidity_event(event, controller)

                except (KeyError, ValueError, TypeError):
                    logger.exception("Failed to parse alert event")
                except Exception:
                    logger.exception("Failed to handle humidity event")
    finally:
        await controller.close()

    logger.info("Smart plug service stopped")


def main() -> None:
    """Entry point for the smart plug service."""
    configure()

    if not get_settings().smartplug.enabled:
        logger.info("Smart plug service is disabled, exiting")
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
