"""Notification system for sensor alerts.

Provides an abstract notification interface with pluggable backends.
Currently supports Gmail notifications.
"""
import ssl
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
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
from rpi.dht.models import Measure

logger = logging.getLogger("notifications")

MESSAGE_TEMPLATE = (
    "Sensor alert! A threshold has been crossed at {recording_time}, "
    "value recorded: {value}, threshold {threshold_name} bound was: "
    "{threshold}{unit}."
)


@dataclass(frozen=True)
class Event:
    """A notification event triggered when a threshold is crossed."""
    measure: Measure
    threshold: int
    recording_time: datetime

    @property
    def threshold_name(self) -> str:
        """Return a human-readable name for the threshold."""
        return str(self.threshold)


class Notifier(Protocol):
    """Protocol for notification backends."""

    def send(self, event: Event) -> None:
        """Send a notification for the given event."""
        ...


class AbstractNotifier(ABC):
    """Abstract base class for notification backends."""

    def format_message(self, event: Event) -> str:
        """Format the notification message."""
        return MESSAGE_TEMPLATE.format(
            threshold_name=event.threshold_name,
            value=str(event.measure),
            unit=event.measure.unit,
            **asdict(event)
        )

    @abstractmethod
    def send(self, event: Event) -> None:
        """Send a notification for the given event."""
        ...


class GmailNotifier(AbstractNotifier):
    """Gmail notification backend."""

    def _build_message(self, event: Event) -> EmailMessage:
        """Build the email message."""
        msg = EmailMessage()
        msg.add_header("From", GmailConfig.SENDER)
        msg.add_header("To", GmailConfig.RECIPIENTS)
        msg.add_header("Subject", GmailConfig.SUBJECT)
        msg.set_content(self.format_message(event))
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
                # Network-related errors (connection refused, timeout, etc.)
                last_error = e
                backoff = EMAIL_INITIAL_BACKOFF_SEC * (2 ** attempt)
                logger.warning(
                    "Email send attempt %d/%d failed (network error): %s. "
                    "Retrying in %ds...",
                    attempt + 1, EMAIL_MAX_RETRIES, e, backoff)
                sleep(backoff)
            except Exception as e:
                # Auth errors or other SMTP errors - don't retry
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
    """Factory function to get the configured notifier.

    Returns GmailNotifier if notifications are enabled, otherwise NoOpNotifier.
    """
    if NOTIFICATION_SERVICE_ENABLED:
        return GmailNotifier()
    return NoOpNotifier()
