"""Notification service that listens to alert events and sends notifications.

Subscribes to the event bus ALERT topic and dispatches notifications
via configured backends (Gmail, Slack, etc.).
"""
import asyncio
import signal
from datetime import datetime

from rpi.lib.alerts import AlertEvent, Namespace
from rpi.lib.config import get_settings
from rpi.lib.eventbus import EventSubscriber, Topic
from rpi.lib.notifications import get_notifier
from rpi.logging import configure, get_logger

logger = get_logger("notifications.service")


def _parse_alert_event(data: dict) -> AlertEvent:
    """Parse alert event data from the event bus."""
    return AlertEvent(
        namespace=Namespace(data["namespace"]),
        sensor_name=data["sensor_name"],
        value=data["value"],
        unit=data["unit"],
        threshold=data["threshold"],
        recording_time=datetime.strptime(data["recording_time"], "%Y-%m-%d %H:%M:%S"),
        is_resolved=data["is_resolved"],
    )


async def run() -> None:
    """Run the notification service."""
    settings = get_settings()

    if not settings.eventbus.enabled:
        logger.warning("Event bus disabled, notification service exiting")
        return

    subscriber = EventSubscriber(topics=[Topic.ALERT])
    subscriber.connect()
    notifier = get_notifier()

    logger.info("Notification service started")

    try:
        async for topic, data in subscriber.receive():
            try:
                event = _parse_alert_event(data)
                event_type = "resolution" if event.is_resolved else "alert"
                logger.info("Processing %s for %s", event_type, event.sensor_name)
                await notifier.send(event)
            except Exception as e:
                logger.error("Failed to process notification: %s", e)
    finally:
        subscriber.close()
        logger.info("Notification service stopped")


def main() -> None:
    """Entry point for the notification service."""
    configure()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Handle shutdown signals
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, loop.stop)

    try:
        loop.run_until_complete(run())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
