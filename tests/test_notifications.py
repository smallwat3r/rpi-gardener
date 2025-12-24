"""Tests for the notification system."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from rpi.lib.notifications import (
    Event,
    GmailNotifier,
    NoOpNotifier,
    get_notifier,
)


class TestEvent:
    """Tests for the Event dataclass."""

    def test_event_creation(self, frozen_time):
        event = Event(
            sensor_name="temperature",
            value=30.5,
            unit="c",
            threshold=25,
            recording_time=frozen_time,
        )

        assert event.sensor_name == "temperature"
        assert event.value == 30.5
        assert event.unit == "c"
        assert event.threshold == 25

    def test_event_immutable(self, frozen_time):
        event = Event(
            sensor_name="temperature",
            value=30.5,
            unit="c",
            threshold=25,
            recording_time=frozen_time,
        )

        with pytest.raises(AttributeError):
            event.value = 40.0

    def test_format_message(self, frozen_time):
        event = Event(
            sensor_name="humidity",
            value=75.0,
            unit="%",
            threshold=65,
            recording_time=frozen_time,
        )

        message = event.format_message()

        assert "humidity" in message
        assert "75.0%" in message
        assert "65%" in message
        assert "threshold" in message.lower()


class TestGmailNotifier:
    """Tests for the Gmail notification backend."""

    @patch("rpi.lib.notifications.SMTP")
    @patch("rpi.lib.notifications.ssl.create_default_context")
    def test_successful_send(self, mock_ssl, mock_smtp, frozen_time):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        event = Event(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = GmailNotifier()
        notifier.send(event)

        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()

    @patch("rpi.lib.notifications.SMTP")
    @patch("rpi.lib.notifications.ssl.create_default_context")
    @patch("rpi.lib.notifications.sleep")
    def test_retry_on_network_error(self, mock_sleep, mock_ssl, mock_smtp, frozen_time):
        mock_server = MagicMock()
        mock_server.send_message.side_effect = [OSError("Network error"), None]
        mock_smtp.return_value.__enter__.return_value = mock_server

        event = Event(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = GmailNotifier()
        notifier.send(event)

        # Should have retried
        assert mock_server.send_message.call_count == 2
        mock_sleep.assert_called_once()

    @patch("rpi.lib.notifications.SMTP")
    @patch("rpi.lib.notifications.ssl.create_default_context")
    def test_no_retry_on_non_network_error(self, mock_ssl, mock_smtp, frozen_time):
        mock_server = MagicMock()
        mock_server.send_message.side_effect = ValueError("Bad data")
        mock_smtp.return_value.__enter__.return_value = mock_server

        event = Event(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = GmailNotifier()
        notifier.send(event)

        # Should not retry for non-network errors
        assert mock_server.send_message.call_count == 1

    def test_build_message(self, frozen_time):
        event = Event(
            sensor_name="humidity",
            value=75.0,
            unit="%",
            threshold=65,
            recording_time=frozen_time,
        )

        notifier = GmailNotifier()
        message = notifier._build_message(event)

        assert message["Subject"] is not None
        assert event.format_message() in message.get_content()


class TestNoOpNotifier:
    """Tests for the no-op notification backend."""

    def test_send_logs_only(self, frozen_time, caplog):
        event = Event(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = NoOpNotifier()
        notifier.send(event)

        assert "disabled" in caplog.text.lower()


class TestGetNotifier:
    """Tests for the notifier factory function."""

    @patch("rpi.lib.notifications.NOTIFICATION_SERVICE_ENABLED", True)
    def test_returns_gmail_when_enabled(self):
        notifier = get_notifier()
        assert isinstance(notifier, GmailNotifier)

    @patch("rpi.lib.notifications.NOTIFICATION_SERVICE_ENABLED", False)
    def test_returns_noop_when_disabled(self):
        notifier = get_notifier()
        assert isinstance(notifier, NoOpNotifier)
