"""Notification system for sensor alerts.

Provides an abstract notification interface with pluggable backends.
Currently supports Gmail notifications.
"""
import ssl
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from smtplib import SMTP
from time import sleep
from typing import Protocol

from rpi import logging
from rpi.lib.config import (
    EMAIL_INITIAL_BACKOFF_SEC,
    EMAIL_MAX_RETRIES,
    EMAIL_TIMEOUT_SEC,
    GmailConfig,
    NOTIFICATION_SERVICE_ENABLED,
)

logger = logging.getLogger("notifications")

MESSAGE_TEMPLATE = (
    "Sensor alert! {sensor_name} crossed threshold at {recording_time}. "
    "Value: {value}{unit}, threshold: {threshold}{unit}."
)


@dataclass(frozen=True)
class Event:
    """A notification event triggered when a threshold is crossed."""
    sensor_name: str
    value: float
    unit: str
    threshold: float
    recording_time: datetime

    def format_message(self) -> str:
        """Format the notification message."""
        return MESSAGE_TEMPLATE.format(
            sensor_name=self.sensor_name,
            value=self.value,
            unit=self.unit,
            threshold=self.threshold,
            recording_time=self.recording_time,
        )


class Notifier(Protocol):
    """Protocol for notification backends."""

    def send(self, event: Event) -> None:
        """Send a notification for the given event."""


class AbstractNotifier(ABC):
    """Abstract base class for notification backends."""

    @abstractmethod
    def send(self, event: Event) -> None:
        """Send a notification for the given event."""


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
        last_error: Exception | None = None

        for attempt in range(EMAIL_MAX_RETRIES):
            try:
                context = ssl.create_default_context()
                with SMTP("smtp.gmail.com", 587, timeout=EMAIL_TIMEOUT_SEC) as server:
                    server.starttls(context=context)
                    server.login(GmailConfig.USERNAME, GmailConfig.PASSWORD)
                    server.send_message(message)
                logger.info("Sent email notification for event %s", id(event))
                return
            except OSError as e:
                last_error = e
                backoff = EMAIL_INITIAL_BACKOFF_SEC * (2 ** attempt)
                logger.warning(
                    "Email send attempt %d/%d failed (network error): %s. "
                    "Retrying in %ds...",
                    attempt + 1, EMAIL_MAX_RETRIES, e, backoff)
                sleep(backoff)
            except Exception as e:
                logger.error("Email send failed (non-retryable): %s", e)
                return

        logger.error(
            "Email send failed after %d attempts. Last error: %s",
            EMAIL_MAX_RETRIES, last_error)


class NoOpNotifier(AbstractNotifier):
    """No-op notifier that logs but doesn't send notifications."""

    def send(self, event: Event) -> None:
        """Log the event but don't send a notification."""
        logger.info("Notification service disabled, ignoring event %s", id(event))


def get_notifier() -> AbstractNotifier:
    """Factory function to get the configured notifier."""
    if NOTIFICATION_SERVICE_ENABLED:
        return GmailNotifier()
    return NoOpNotifier()
