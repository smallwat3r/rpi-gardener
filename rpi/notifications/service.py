"""Notification service that listens to alert events and sends notifications.

Subscribes to the event bus ALERT topic and dispatches notifications
via configured backends (Gmail, Slack, etc.).
"""

import asyncio
import signal
from contextlib import suppress

from rpi.lib.alerts import AlertEvent
from rpi.lib.eventbus import EventSubscriber, Topic
from rpi.lib.notifications import get_notifier, get_sensor_label
from rpi.logging import configure, get_logger

logger = get_logger("notifications.service")


async def run() -> None:
    """Run the notification service."""
    async with EventSubscriber(topics=[Topic.ALERT]) as subscriber:
        logger.info("Notification service started")
        async for _topic, data in subscriber.receive():
            try:
                event = AlertEvent.from_dict(data)
                label = get_sensor_label(event.sensor_name)
                event_type = "resolution" if event.is_resolved else "alert"
                logger.info("Processing %s for %s", event_type, label)
                # Get notifier for each event to pick up latest settings
                notifier = await get_notifier()
                await notifier.send(event)
            except (KeyError, ValueError, TypeError):
                logger.exception("Failed to parse alert event")
            except OSError:
                logger.exception("Failed to send notification")

    logger.info("Notification service stopped")


def main() -> None:
    """Entry point for the notification service."""
    configure()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Handle shutdown signals
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, loop.stop)

    with suppress(KeyboardInterrupt):
        loop.run_until_complete(run())
    loop.close()


if __name__ == "__main__":
    main()
