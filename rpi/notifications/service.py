"""Notification service that listens to alert events and sends notifications.

Subscribes to the event bus ALERT topic and dispatches notifications
via configured backends (Gmail, Slack, etc.).
"""

import asyncio
import signal
from datetime import datetime
from typing import Any

from rpi.lib.alerts import AlertEvent, Namespace
from rpi.lib.eventbus import EventSubscriber, Topic
from rpi.lib.notifications import get_notifier, get_sensor_label
from rpi.logging import configure, get_logger

logger = get_logger("notifications.service")


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


async def run() -> None:
    """Run the notification service."""
    subscriber = EventSubscriber(topics=[Topic.ALERT])
    await subscriber.connect()
    notifier = get_notifier()

    logger.info("Notification service started")

    try:
        async for _topic, data in subscriber.receive():
            try:
                event = _parse_alert_event(data)
                label = get_sensor_label(event.sensor_name)
                event_type = "resolution" if event.is_resolved else "alert"
                logger.info("Processing %s for %s", event_type, label)
                await notifier.send(event)
            except (KeyError, ValueError, TypeError) as e:
                logger.error("Failed to parse alert event: %s", e)
            except OSError as e:
                logger.error("Failed to send notification: %s", e)
    finally:
        await subscriber.close()
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
