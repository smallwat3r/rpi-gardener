"""Humidifier service that controls humidity via a TP-Link Kasa smart plug.

Subscribes to the event bus ALERT topic and controls a smart plug
to turn a humidifier on/off based on humidity levels.

- Humidifier turns ON when humidity is too LOW (alert triggered)
- Humidifier turns OFF when humidity recovers (alert resolved)
"""

import asyncio
import signal
from contextlib import suppress

from rpi.lib.alerts import AlertEvent, Namespace
from rpi.lib.config import MeasureName, get_settings
from rpi.lib.eventbus import EventSubscriber, Topic
from rpi.lib.smartplug import SmartPlugProtocol, create_smartplug_controller
from rpi.logging import configure, get_logger

logger = get_logger("humidifier.service")


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
    """Handle a humidity alert by controlling the humidifier."""
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
    """Run the humidifier service."""
    cfg = get_settings().humidifier

    if not cfg.host:
        logger.warning("HUMIDIFIER_HOST not configured, service exiting")
        return

    controller = create_smartplug_controller(cfg.host)

    async with controller, EventSubscriber(topics=[Topic.ALERT]) as subscriber:
        logger.info("Humidifier service started")
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

    logger.info("Humidifier service stopped")


def main() -> None:
    """Entry point for the humidifier service."""
    configure()

    if not get_settings().humidifier.enabled:
        logger.info("Humidifier service is disabled, exiting")
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
