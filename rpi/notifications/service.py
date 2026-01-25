"""Notification service that listens to alert events and sends notifications.

Subscribes to the event bus ALERT topic and dispatches notifications
via configured backends (Gmail, Slack, etc.).
"""

from rpi.lib.alerts import safe_parse_alert_event
from rpi.lib.eventbus import EventSubscriber, Topic
from rpi.lib.notifications import get_notifier, get_sensor_label
from rpi.lib.service import run_service
from rpi.logging import get_logger

logger = get_logger("notifications.service")


async def run() -> None:
    """Run the notification service."""
    async with EventSubscriber(topics=[Topic.ALERT]) as subscriber:
        logger.info("Notification service started")
        async for _topic, data in subscriber.receive():
            event = safe_parse_alert_event(data)
            if event is None:
                continue
            try:
                label = get_sensor_label(event.sensor_name)
                event_type = "resolution" if event.is_resolved else "alert"
                logger.info("Processing %s for %s", event_type, label)
                # Get notifier for each event to pick up latest settings
                notifier = await get_notifier()
                await notifier.send(event)
            except OSError:
                logger.exception("Failed to send notification")

    logger.info("Notification service stopped")


def main() -> None:
    """Entry point for the notification service."""
    run_service(run, name="notifications")


if __name__ == "__main__":
    main()
