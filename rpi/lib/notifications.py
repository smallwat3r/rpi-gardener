"""Notification system for sensor alerts.

Provides an abstract notification interface with pluggable backends.
Supports Gmail and Slack notifications, or both simultaneously.
"""
import asyncio
import json
import ssl
import urllib.request
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from smtplib import SMTP
from time import sleep
from typing import Callable

from rpi import logging
from rpi.lib.config import (
    EMAIL_INITIAL_BACKOFF_SEC,
    EMAIL_MAX_RETRIES,
    EMAIL_TIMEOUT_SEC,
    GmailConfig,
    MeasureName,
    NotificationBackend,
    NOTIFICATION_BACKENDS,
    NOTIFICATION_SERVICE_ENABLED,
    PlantId,
    SlackConfig,
)

logger = logging.getLogger("notifications")

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="notifier")

SENSOR_LABELS = {
    MeasureName.TEMPERATURE: "Temperature",
    MeasureName.HUMIDITY: "Humidity",
    PlantId.PLANT_1: "Plant 1",
    PlantId.PLANT_2: "Plant 2",
    PlantId.PLANT_3: "Plant 3",
}


@dataclass(frozen=True)
class Event:
    """A notification event triggered when a threshold is crossed."""
    sensor_name: str
    value: float
    unit: str
    threshold: float
    recording_time: datetime

    @property
    def label(self) -> str:
        """Human-readable sensor label."""
        return SENSOR_LABELS.get(self.sensor_name, self.sensor_name.replace("-", " ").title())

    def format_message(self) -> str:
        """Format the notification message for email/plain text."""
        time_str = self.recording_time.strftime("%H:%M:%S")
        return (
            f"{self.label} alert!\n\n"
            f"Current value: {self.value:.1f}{self.unit}\n"
            f"Threshold: {self.threshold:.0f}{self.unit}\n"
            f"Time: {time_str}"
        )


class AbstractNotifier(ABC):
    """Abstract base class for notification backends."""

    @abstractmethod
    def send(self, event: Event) -> None:
        """Send a notification for the given event (blocking)."""

    async def send_async(self, event: Event) -> None:
        """Send a notification asynchronously without blocking the event loop."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(_executor, self.send, event)

    def _send_with_retry(self, send_fn: Callable[[], None], backend_name: str) -> None:
        """Execute send function with retry logic and exponential backoff."""
        last_error: Exception | None = None

        for attempt in range(EMAIL_MAX_RETRIES):
            try:
                send_fn()
                return
            except OSError as e:
                last_error = e
                backoff = EMAIL_INITIAL_BACKOFF_SEC * (2 ** attempt)
                logger.warning(
                    "%s send attempt %d/%d failed: %s. Retrying in %ds...",
                    backend_name, attempt + 1, EMAIL_MAX_RETRIES, e, backoff)
                sleep(backoff)
            except Exception as e:
                logger.error("%s send failed (non-retryable): %s", backend_name, e)
                return

        logger.error(
            "%s send failed after %d attempts. Last error: %s",
            backend_name, EMAIL_MAX_RETRIES, last_error)


class GmailNotifier(AbstractNotifier):
    """Gmail notification backend."""

    def _build_message(self, event: Event) -> EmailMessage:
        """Build the email message."""
        msg = EmailMessage()
        msg.add_header("From", GmailConfig.SENDER)
        msg.add_header("To", GmailConfig.RECIPIENTS)
        msg.add_header("Subject", GmailConfig.SUBJECT)
        msg.set_content(event.format_message())
        return msg

    def send(self, event: Event) -> None:
        """Send the email with retry logic and exponential backoff."""
        message = self._build_message(event)

        def do_send() -> None:
            context = ssl.create_default_context()
            with SMTP("smtp.gmail.com", 587, timeout=EMAIL_TIMEOUT_SEC) as server:
                server.starttls(context=context)
                server.login(GmailConfig.USERNAME, GmailConfig.PASSWORD)
                server.send_message(message)
            logger.info("Sent email notification for event %s", id(event))

        self._send_with_retry(do_send, "Email")


class SlackNotifier(AbstractNotifier):
    """Slack webhook notification backend."""

    def _build_payload(self, event: Event) -> dict:
        """Build the Slack message payload."""
        time_str = event.recording_time.strftime("%H:%M:%S")
        return {
            "text": f"{event.label} alert!",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"{event.label} Alert"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Current:*\n{event.value:.1f}{event.unit}"},
                        {"type": "mrkdwn", "text": f"*Threshold:*\n{event.threshold:.0f}{event.unit}"},
                    ]
                },
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f":clock1: {time_str}"}]
                }
            ]
        }

    def send(self, event: Event) -> None:
        """Send notification to Slack webhook with retry logic."""
        payload = self._build_payload(event)
        data = json.dumps(payload).encode("utf-8")

        def do_send() -> None:
            req = urllib.request.Request(
                SlackConfig.WEBHOOK_URL,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=EMAIL_TIMEOUT_SEC) as resp:
                if resp.status != 200:
                    raise OSError(f"Slack API returned status {resp.status}")
            logger.info("Sent Slack notification for event %s", id(event))

        self._send_with_retry(do_send, "Slack")


class CompositeNotifier(AbstractNotifier):
    """Sends notifications to multiple backends."""

    def __init__(self, notifiers: list[AbstractNotifier]):
        self._notifiers = notifiers

    def send(self, event: Event) -> None:
        """Send notification to all configured backends."""
        for notifier in self._notifiers:
            notifier.send(event)


class NoOpNotifier(AbstractNotifier):
    """No-op notifier that logs but doesn't send notifications."""

    def send(self, event: Event) -> None:
        """Log the event but don't send a notification."""
        logger.info("Notification service disabled, ignoring event %s", id(event))


_BACKEND_MAP: dict[NotificationBackend, type[AbstractNotifier]] = {
    NotificationBackend.GMAIL: GmailNotifier,
    NotificationBackend.SLACK: SlackNotifier,
}


def get_notifier() -> AbstractNotifier:
    """Factory function to get the configured notifier."""
    if not NOTIFICATION_SERVICE_ENABLED:
        return NoOpNotifier()

    notifiers = []
    for backend in NOTIFICATION_BACKENDS:
        if backend in _BACKEND_MAP:
            notifiers.append(_BACKEND_MAP[backend]())
        else:
            logger.warning("Unknown notification backend: %s", backend)

    if not notifiers:
        return NoOpNotifier()
    if len(notifiers) == 1:
        return notifiers[0]
    return CompositeNotifier(notifiers)
