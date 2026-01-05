"""Smart plug service that controls a humidifier based on humidity alerts.

Subscribes to the event bus ALERT topic and controls a TP-Link Kasa
smart plug to turn a humidifier on/off based on humidity levels.

- Humidifier turns ON when humidity is too LOW (alert triggered)
- Humidifier turns OFF when humidity recovers (alert resolved)
"""

import asyncio
import signal
from contextlib import suppress
from datetime import datetime
from typing import Any

from rpi.lib.alerts import AlertEvent, Namespace
from rpi.lib.config import MeasureName, get_settings
from rpi.lib.eventbus import EventSubscriber, Topic
from rpi.lib.smartplug import SmartPlugProtocol, get_smartplug_controller
from rpi.logging import configure, get_logger

logger = get_logger("smartplug.service")


def _parse_alert_event(data: dict[str, Any]) -> AlertEvent:
    """Parse alert event data from the event bus."""
    return AlertEvent(
        namespace=Namespace(data["namespace"]),
        sensor_name=data["sensor_name"],
        value=data["value"],
        unit=data["unit"],
        threshold=data["threshold"],
        recording_time=datetime.strptime(
            data["recording_time"], "%Y-%m-%d %H:%M:%S"
        ),
        is_resolved=data["is_resolved"],
    )


def is_low_humidity_alert(event: AlertEvent) -> bool:
    """Check if this is a low humidity alert from DHT sensor.

    We only act on MIN humidity threshold alerts (humidity too low)
    since we're controlling a humidifier.
    """
    # Must be from DHT namespace (not plant moisture from Pico)
    if event.namespace != Namespace.DHT:
        return False

    # Must be humidity sensor
    if event.sensor_name != MeasureName.HUMIDITY:
        return False

    # For resolved alerts, always return True (we need to turn off)
    if event.is_resolved:
        return True

    # For active alerts, only act if value is below threshold (MIN violation)
    # This filters out MAX humidity alerts (too humid)
    if event.threshold is not None:
        return event.value < event.threshold

    return False


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
                    event = _parse_alert_event(data)

                    if not is_low_humidity_alert(event):
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
