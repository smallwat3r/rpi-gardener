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
from typing import Any, override

from rpi.lib.alerts import AlertEvent
from rpi.lib.config import (
    MeasureName,
    NotificationBackend,
    PlantId,
    get_effective_notifications,
    get_settings,
)
from rpi.lib.retry import with_retry
from rpi.logging import get_logger

logger = get_logger("lib.notifications")

SENSOR_LABELS: dict[str | int, tuple[str, str]] = {
    # (label, emoji)
    MeasureName.TEMPERATURE: ("Temperature", "🌡️"),
    MeasureName.HUMIDITY: ("Humidity", "💧"),
    PlantId.PLANT_1: ("Plant 1", "🪴"),
    PlantId.PLANT_2: ("Plant 2", "🪴"),
    PlantId.PLANT_3: ("Plant 3", "🪴"),
}


def get_sensor_info(sensor_name: str | int) -> tuple[str, str]:
    """Get human-readable label and emoji for a sensor."""
    if sensor_name in SENSOR_LABELS:
        return SENSOR_LABELS[sensor_name]
    if isinstance(sensor_name, int):
        return (f"Plant {sensor_name}", "🪴")
    return (str(sensor_name).replace("-", " ").title(), "📊")


def get_sensor_label(sensor_name: str | int) -> str:
    """Get human-readable label for a sensor."""
    return get_sensor_info(sensor_name)[0]


def _get_alert_description(event: AlertEvent) -> str:
    """Get a descriptive message for the alert based on sensor type and value."""
    label, emoji = get_sensor_info(event.sensor_name)
    is_below = event.threshold is not None and event.value < event.threshold

    # Plant/moisture alerts (min threshold only)
    if isinstance(event.sensor_name, int) or str(event.sensor_name).startswith(
        "plant"
    ):
        if event.is_resolved:
            return f"{emoji} {label} is watered"
        return f"{emoji} {label} is thirsty"

    # Temperature alerts
    if event.sensor_name == MeasureName.TEMPERATURE:
        if event.is_resolved:
            return f"{emoji} {label} is back to normal"
        return f"{emoji} {label} is too {'cold' if is_below else 'hot'}"

    # Humidity alerts
    if event.sensor_name == MeasureName.HUMIDITY:
        if event.is_resolved:
            return f"{emoji} {label} is back to normal"
        return f"{emoji} {label} is too {'dry' if is_below else 'humid'}"

    # Generic fallback
    if event.is_resolved:
        return f"{emoji} {label} is back to normal"
    return f"{emoji} {label} alert"


def format_alert_message(event: AlertEvent) -> str:
    """Format an alert event as a notification message."""
    description = _get_alert_description(event)
    time_str = event.recording_time.strftime("%H:%M:%S")

    if event.is_resolved:
        return f"{description}\n\nCurrent value: {event.value:.1f}{event.unit}\nTime: {time_str}"
    return (
        f"{description}!\n\n"
        f"Current value: {event.value:.1f}{event.unit}\n"
        f"Threshold: {event.threshold:.0f}{event.unit}\n"
        f"Time: {time_str}"
    )


class AbstractNotifier(ABC):
    """Abstract base class for notification backends."""

    @abstractmethod
    async def send(self, event: AlertEvent) -> None:
        """Send a notification for the given alert event."""


class GmailNotifier(AbstractNotifier):
    """Gmail notification backend."""

    def _build_email(self, subject: str, body: str) -> EmailMessage:
        """Build an email message with the given subject and body."""
        gmail = get_settings().notifications.gmail
        msg = EmailMessage()
        msg.add_header("From", gmail.sender)
        msg.add_header("To", gmail.recipients)
        msg.add_header("Subject", subject)
        msg.set_content(body)
        return msg

    async def _send_email(
        self, message: EmailMessage, sensor_name: str | int
    ) -> None:
        """Send an email with retry logic and exponential backoff."""
        cfg = get_settings().notifications
        gmail = cfg.gmail
        timeout = cfg.timeout_sec

        def do_send() -> None:
            context = ssl.create_default_context()
            with SMTP("smtp.gmail.com", 587, timeout=timeout) as server:
                server.starttls(context=context)
                server.login(gmail.username, gmail.password.get_secret_value())
                server.send_message(message)
            logger.info("Sent email notification for %s", sensor_name)

        await with_retry(
            do_send,
            name="Email",
            logger=logger,
            max_retries=cfg.max_retries,
            initial_backoff_sec=cfg.initial_backoff_sec,
            run_in_thread=True,
        )

    @override
    async def send(self, event: AlertEvent) -> None:
        """Send email notification."""
        base_subject = get_settings().notifications.gmail.subject
        subject = (
            f"{base_subject} - Resolved" if event.is_resolved else base_subject
        )
        message = self._build_email(subject, format_alert_message(event))
        await self._send_email(message, event.sensor_name)


class SlackNotifier(AbstractNotifier):
    """Slack webhook notification backend."""

    def _build_payload(
        self,
        title: str,
        fields: list[dict[str, str]],
        time_str: str,
    ) -> dict[str, Any]:
        """Build a Slack message payload."""
        return {
            "text": title,
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": title},
                },
                {"type": "section", "fields": fields},
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f":clock1: {time_str}"}
                    ],
                },
            ],
        }

    async def _send_slack(
        self, payload: dict[str, Any], sensor_name: str | int
    ) -> None:
        """Send a Slack message with retry logic."""
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
            logger.info("Sent Slack notification for %s", sensor_name)

        await with_retry(
            do_send,
            name="Slack",
            logger=logger,
            max_retries=cfg.max_retries,
            initial_backoff_sec=cfg.initial_backoff_sec,
            run_in_thread=True,
        )

    @override
    async def send(self, event: AlertEvent) -> None:
        """Send Slack notification."""
        title = _get_alert_description(event)
        time_str = event.recording_time.strftime("%H:%M:%S")

        if event.is_resolved:
            fields = [
                {
                    "type": "mrkdwn",
                    "text": f"*Current:*\n{event.value:.1f}{event.unit}",
                },
            ]
        else:
            fields = [
                {
                    "type": "mrkdwn",
                    "text": f"*Current:*\n{event.value:.1f}{event.unit}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Threshold:*\n{event.threshold:.0f}{event.unit}",
                },
            ]

        payload = self._build_payload(title, fields, time_str)
        await self._send_slack(payload, event.sensor_name)


class CompositeNotifier(AbstractNotifier):
    """Sends notifications to multiple backends."""

    def __init__(self, notifiers: list[AbstractNotifier]):
        self._notifiers = notifiers

    @override
    async def send(self, event: AlertEvent) -> None:
        """Send notification to all configured backends concurrently."""
        results = await asyncio.gather(
            *(notifier.send(event) for notifier in self._notifiers),
            return_exceptions=True,
        )
        for notifier, result in zip(self._notifiers, results, strict=True):
            if isinstance(result, Exception):
                backend_name = notifier.__class__.__name__
                logger.error(
                    "Failed to send %s notification: %s",
                    backend_name,
                    result,
                )


class NoOpNotifier(AbstractNotifier):
    """No-op notifier that logs but doesn't send notifications."""

    @override
    async def send(self, event: AlertEvent) -> None:
        """Log the event but don't send a notification."""
        label = get_sensor_label(event.sensor_name)
        event_type = "resolution" if event.is_resolved else "alert"
        logger.info(
            "Notifications disabled, skipping %s for %s", event_type, label
        )


_BACKEND_MAP: dict[NotificationBackend, type[AbstractNotifier]] = {
    NotificationBackend.GMAIL: GmailNotifier,
    NotificationBackend.SLACK: SlackNotifier,
}


async def get_notifier() -> AbstractNotifier:
    """Factory function to get the configured notifier.

    Fetches effective settings from the database, respecting any overrides
    made via the admin UI. Call this for each notification to pick up
    the latest settings.
    """
    cfg = await get_effective_notifications()
    if not cfg.enabled:
        return NoOpNotifier()

    notifiers: list[AbstractNotifier] = []
    for backend_str in cfg.backends:
        try:
            backend = NotificationBackend(backend_str)
            notifiers.append(_BACKEND_MAP[backend]())
        except (ValueError, KeyError):
            logger.warning("Unknown notification backend: %s", backend_str)

    if not notifiers:
        return NoOpNotifier()
    if len(notifiers) == 1:
        return notifiers[0]
    return CompositeNotifier(notifiers)
