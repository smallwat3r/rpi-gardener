"""Notification system for sensor alerts.

Provides an abstract notification interface with pluggable backends.
Supports Gmail and Slack notifications, or both simultaneously.
"""
import asyncio
import json
import ssl
import urllib.request
from abc import ABC, abstractmethod
from email.message import EmailMessage
from smtplib import SMTP
from typing import TYPE_CHECKING, Callable

from rpi.lib.config import (MeasureName, NotificationBackend, PlantId,
                            get_settings)
from rpi.logging import get_logger

if TYPE_CHECKING:
    from rpi.lib.alerts import ThresholdViolation

logger = get_logger("lib.notifications")

SENSOR_LABELS: dict[str | int, str] = {
    MeasureName.TEMPERATURE: "Temperature",
    MeasureName.HUMIDITY: "Humidity",
    PlantId.PLANT_1: "Plant 1",
    PlantId.PLANT_2: "Plant 2",
    PlantId.PLANT_3: "Plant 3",
}


def get_sensor_label(sensor_name: str | int) -> str:
    """Get human-readable label for a sensor."""
    if sensor_name in SENSOR_LABELS:
        return SENSOR_LABELS[sensor_name]
    if isinstance(sensor_name, int):
        return f"Plant {sensor_name}"
    return str(sensor_name).replace("-", " ").title()


def format_alert_message(violation: "ThresholdViolation") -> str:
    """Format a threshold violation as a notification message."""
    label = get_sensor_label(violation.sensor_name)
    time_str = violation.recording_time.strftime("%H:%M:%S")
    return (
        f"{label} alert!\n\n"
        f"Current value: {violation.value:.1f}{violation.unit}\n"
        f"Threshold: {violation.threshold:.0f}{violation.unit}\n"
        f"Time: {time_str}"
    )


class AbstractNotifier(ABC):
    """Abstract base class for notification backends."""

    @abstractmethod
    async def send(self, violation: "ThresholdViolation") -> None:
        """Send a notification for the given violation."""

    async def _send_with_retry(
        self,
        send_fn: Callable[[], None],
        backend_name: str,
    ) -> None:
        """Execute send function with retry logic and exponential backoff.

        Runs the blocking send_fn in a thread and uses async sleep for backoff,
        ensuring retries don't block other async tasks.
        """
        last_error: Exception | None = None
        max_retries = get_settings().notifications.max_retries

        for attempt in range(max_retries):
            try:
                await asyncio.to_thread(send_fn)
                return
            except OSError as e:
                last_error = e
                backoff = get_settings().notifications.initial_backoff_sec * (2 ** attempt)
                logger.warning(
                    "%s send attempt %d/%d failed: %s. Retrying in %ds...",
                    backend_name, attempt + 1, max_retries, e, backoff)
                await asyncio.sleep(backoff)
            except Exception as e:
                logger.error("%s send failed (non-retryable): %s", backend_name, e)
                return

        logger.error(
            "%s send failed after %d attempts. Last error: %s",
            backend_name, max_retries, last_error)


class GmailNotifier(AbstractNotifier):
    """Gmail notification backend."""

    def _build_message(self, violation: "ThresholdViolation") -> EmailMessage:
        """Build the email message."""
        gmail = get_settings().notifications.gmail
        msg = EmailMessage()
        msg.add_header("From", gmail.sender)
        msg.add_header("To", gmail.recipients)
        msg.add_header("Subject", gmail.subject)
        msg.set_content(format_alert_message(violation))
        return msg

    async def send(self, violation: "ThresholdViolation") -> None:
        """Send the email with retry logic and exponential backoff."""
        message = self._build_message(violation)
        cfg = get_settings().notifications
        gmail = cfg.gmail
        timeout = cfg.timeout_sec

        def do_send() -> None:
            context = ssl.create_default_context()
            with SMTP("smtp.gmail.com", 587, timeout=timeout) as server:
                server.starttls(context=context)
                server.login(gmail.username, gmail.password)
                server.send_message(message)
            logger.info("Sent email notification for %s", violation.sensor_name)

        await self._send_with_retry(do_send, "Email")


class SlackNotifier(AbstractNotifier):
    """Slack webhook notification backend."""

    def _build_payload(self, violation: "ThresholdViolation") -> dict:
        """Build the Slack message payload."""
        label = get_sensor_label(violation.sensor_name)
        time_str = violation.recording_time.strftime("%H:%M:%S")
        return {
            "text": f"{label} alert!",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"{label} Alert"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Current:*\n{violation.value:.1f}{violation.unit}"},
                        {"type": "mrkdwn", "text": f"*Threshold:*\n{violation.threshold:.0f}{violation.unit}"},
                    ]
                },
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f":clock1: {time_str}"}]
                }
            ]
        }

    async def send(self, violation: "ThresholdViolation") -> None:
        """Send notification to Slack webhook with retry logic."""
        payload = self._build_payload(violation)
        data = json.dumps(payload).encode("utf-8")
        cfg = get_settings().notifications
        webhook_url = cfg.slack.webhook_url
        timeout = cfg.timeout_sec

        def do_send() -> None:
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    raise OSError(f"Slack API returned status {resp.status}")
            logger.info("Sent Slack notification for %s", violation.sensor_name)

        await self._send_with_retry(do_send, "Slack")


class CompositeNotifier(AbstractNotifier):
    """Sends notifications to multiple backends."""

    def __init__(self, notifiers: list[AbstractNotifier]):
        self._notifiers = notifiers

    async def send(self, violation: "ThresholdViolation") -> None:
        """Send notification to all configured backends concurrently."""
        await asyncio.gather(
            *(notifier.send(violation) for notifier in self._notifiers),
            return_exceptions=True,
        )


class NoOpNotifier(AbstractNotifier):
    """No-op notifier that logs but doesn't send notifications."""

    async def send(self, violation: "ThresholdViolation") -> None:
        """Log the violation but don't send a notification."""
        logger.info("Notification service disabled, ignoring alert for %s", violation.sensor_name)


_BACKEND_MAP: dict[NotificationBackend, type[AbstractNotifier]] = {
    NotificationBackend.GMAIL: GmailNotifier,
    NotificationBackend.SLACK: SlackNotifier,
}


def get_notifier() -> AbstractNotifier:
    """Factory function to get the configured notifier."""
    cfg = get_settings().notifications
    if not cfg.enabled:
        return NoOpNotifier()

    notifiers = []
    for backend in cfg.backends:
        if backend in _BACKEND_MAP:
            notifiers.append(_BACKEND_MAP[backend]())
        else:
            logger.warning("Unknown notification backend: %s", backend)

    if not notifiers:
        return NoOpNotifier()
    if len(notifiers) == 1:
        return notifiers[0]
    return CompositeNotifier(notifiers)
