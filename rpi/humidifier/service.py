"""Humidifier service that controls humidity via a TP-Link Kasa smart plug.

Subscribes to the event bus ALERT topic and controls a smart plug
to turn a humidifier on/off based on humidity levels.

- Humidifier turns ON when humidity is too LOW (alert triggered)
- Humidifier turns OFF when humidity recovers (alert resolved)
- Humidifier turns OFF on service shutdown (safety measure)
"""

from datetime import UTC, datetime

from rpi.lib.alerts import AlertEvent, Namespace, safe_parse_alert_event
from rpi.lib.config import MeasureName, get_settings
from rpi.lib.eventbus import (
    EventPublisher,
    EventSubscriber,
    HumidifierStateEvent,
    Topic,
)
from rpi.lib.service import run_service
from rpi.lib.smartplug import SmartPlugProtocol, create_smartplug_controller
from rpi.logging import get_logger

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
    event: AlertEvent,
    controller: SmartPlugProtocol,
    publisher: EventPublisher,
) -> None:
    """Handle a humidity alert by controlling the humidifier."""
    if event.is_resolved:
        logger.info(
            "Humidity recovered to %.1f%% - turning OFF humidifier",
            event.value,
        )
        success = await controller.turn_off()
        is_on = False
    else:
        logger.info(
            "Humidity too low at %.1f%% (threshold: %.0f%%) - "
            "turning ON humidifier",
            event.value,
            event.threshold,
        )
        success = await controller.turn_on()
        is_on = True

    if success:
        publisher.publish(
            HumidifierStateEvent(is_on=is_on, recording_time=datetime.now(UTC))
        )


async def run() -> None:
    """Run the humidifier service."""
    cfg = get_settings().humidifier

    if not cfg.host:
        logger.warning("HUMIDIFIER_HOST not configured, service exiting")
        return

    # turn_off_on_close ensures humidifier is OFF when service stops
    controller = create_smartplug_controller(cfg.host, turn_off_on_close=True)

    with EventPublisher() as publisher:
        async with (
            controller,
            EventSubscriber(topics=[Topic.ALERT]) as subscriber,
        ):
            logger.info("Humidifier service started")
            async for _topic, data in subscriber.receive():
                event = safe_parse_alert_event(data)
                if event is None:
                    continue
                if _is_low_humidity_alert(event):
                    await _handle_humidity_event(event, controller, publisher)

    logger.info("Humidifier service stopped")


def main() -> None:
    """Entry point for the humidifier service."""
    run_service(
        run,
        enabled=lambda: get_settings().humidifier.enabled,
        name="humidifier",
    )


if __name__ == "__main__":
    main()
