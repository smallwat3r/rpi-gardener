"""Tests for the notification system."""
from unittest.mock import MagicMock, patch

import pytest

from rpi.lib.alerts import Namespace, ThresholdViolation
from rpi.lib.notifications import (CompositeNotifier, GmailNotifier,
                                   NoOpNotifier, SlackNotifier,
                                   format_alert_message, get_notifier,
                                   get_sensor_label)


def make_violation(
    sensor_name="temperature",
    value=30.5,
    unit="c",
    threshold=25,
    recording_time=None,
    namespace=Namespace.DHT,
):
    """Create a ThresholdViolation for testing."""
    from datetime import datetime, timezone
    if recording_time is None:
        recording_time = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    return ThresholdViolation(
        namespace=namespace,
        sensor_name=sensor_name,
        value=value,
        unit=unit,
        threshold=threshold,
        recording_time=recording_time,
    )


class TestThresholdViolation:
    """Tests for the ThresholdViolation dataclass."""

    def test_violation_creation(self, frozen_time):
        violation = make_violation(
            sensor_name="temperature",
            value=30.5,
            unit="c",
            threshold=25,
            recording_time=frozen_time,
        )

        assert violation.sensor_name == "temperature"
        assert violation.value == 30.5
        assert violation.unit == "c"
        assert violation.threshold == 25
        assert violation.namespace == Namespace.DHT

    def test_format_message(self, frozen_time):
        violation = make_violation(
            sensor_name="humidity",
            value=75.0,
            unit="%",
            threshold=65,
            recording_time=frozen_time,
        )

        message = format_alert_message(violation)

        assert "Humidity" in message
        assert "75.0%" in message
        assert "65%" in message
        assert "12:00:00" in message

    def test_label_from_sensor_labels(self, frozen_time):
        violation = make_violation(
            sensor_name="temperature",
            value=30.0,
            unit="c",
            threshold=25,
            recording_time=frozen_time,
        )
        assert get_sensor_label(violation.sensor_name) == "Temperature"

    def test_label_fallback(self, frozen_time):
        violation = make_violation(
            sensor_name="custom-sensor",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )
        assert get_sensor_label(violation.sensor_name) == "Custom Sensor"


class TestGmailNotifier:
    """Tests for the Gmail notification backend."""

    @patch("rpi.lib.notifications.SMTP")
    @patch("rpi.lib.notifications.ssl.create_default_context")
    def test_successful_send(self, mock_ssl, mock_smtp, frozen_time):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        violation = make_violation(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = GmailNotifier()
        notifier.send(violation)

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

        violation = make_violation(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = GmailNotifier()
        notifier.send(violation)

        assert mock_server.send_message.call_count == 2
        mock_sleep.assert_called_once()

    @patch("rpi.lib.notifications.SMTP")
    @patch("rpi.lib.notifications.ssl.create_default_context")
    def test_no_retry_on_non_network_error(self, mock_ssl, mock_smtp, frozen_time):
        mock_server = MagicMock()
        mock_server.send_message.side_effect = ValueError("Bad data")
        mock_smtp.return_value.__enter__.return_value = mock_server

        violation = make_violation(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = GmailNotifier()
        notifier.send(violation)

        assert mock_server.send_message.call_count == 1

    def test_build_message(self, frozen_time):
        violation = make_violation(
            sensor_name="humidity",
            value=75.0,
            unit="%",
            threshold=65,
            recording_time=frozen_time,
        )

        notifier = GmailNotifier()
        message = notifier._build_message(violation)

        assert message["Subject"] is not None
        assert format_alert_message(violation) in message.get_content()


class TestSlackNotifier:
    """Tests for the Slack notification backend."""

    @patch("rpi.lib.notifications.urllib.request.urlopen")
    @patch("rpi.lib.notifications.urllib.request.Request")
    def test_successful_send(self, mock_request, mock_urlopen, frozen_time):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        violation = make_violation(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = SlackNotifier()
        notifier.send(violation)

        mock_request.assert_called_once()
        mock_urlopen.assert_called_once()

    @patch("rpi.lib.notifications.urllib.request.urlopen")
    @patch("rpi.lib.notifications.urllib.request.Request")
    @patch("rpi.lib.notifications.sleep")
    def test_retry_on_network_error(self, mock_sleep, mock_request, mock_urlopen, frozen_time):
        mock_success = MagicMock()
        mock_success.status = 200
        mock_urlopen.side_effect = [
            OSError("Network error"),
            MagicMock(__enter__=MagicMock(return_value=mock_success))
        ]

        violation = make_violation(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = SlackNotifier()
        notifier.send(violation)

        assert mock_urlopen.call_count == 2
        mock_sleep.assert_called_once()

    @patch("rpi.lib.notifications.urllib.request.urlopen")
    @patch("rpi.lib.notifications.urllib.request.Request")
    def test_no_retry_on_non_network_error(self, mock_request, mock_urlopen, frozen_time):
        mock_urlopen.side_effect = ValueError("Bad data")

        violation = make_violation(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = SlackNotifier()
        notifier.send(violation)

        assert mock_urlopen.call_count == 1

    def test_build_payload(self, frozen_time):
        violation = make_violation(
            sensor_name="humidity",
            value=75.0,
            unit="%",
            threshold=65,
            recording_time=frozen_time,
        )

        notifier = SlackNotifier()
        payload = notifier._build_payload(violation)

        assert payload["text"] == "Humidity alert!"
        assert payload["blocks"][0]["type"] == "header"
        assert "Humidity Alert" in payload["blocks"][0]["text"]["text"]
        # Check fields section
        fields = payload["blocks"][1]["fields"]
        assert "75.0%" in fields[0]["text"]
        assert "65%" in fields[1]["text"]


class TestCompositeNotifier:
    """Tests for the composite notification backend."""

    def test_sends_to_all_backends(self, frozen_time):
        mock_notifier1 = MagicMock()
        mock_notifier2 = MagicMock()

        violation = make_violation(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        composite = CompositeNotifier([mock_notifier1, mock_notifier2])
        composite.send(violation)

        mock_notifier1.send.assert_called_once_with(violation)
        mock_notifier2.send.assert_called_once_with(violation)


class TestNoOpNotifier:
    """Tests for the no-op notification backend."""

    def test_send_logs_only(self, frozen_time, caplog):
        violation = make_violation(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = NoOpNotifier()
        notifier.send(violation)

        assert "disabled" in caplog.text.lower()


class TestGetNotifier:
    """Tests for the notifier factory function."""

    @patch("rpi.lib.notifications.NOTIFICATION_BACKENDS", ["gmail"])
    @patch("rpi.lib.notifications.NOTIFICATION_SERVICE_ENABLED", True)
    def test_returns_gmail_when_configured(self):
        notifier = get_notifier()
        assert isinstance(notifier, GmailNotifier)

    @patch("rpi.lib.notifications.NOTIFICATION_BACKENDS", ["slack"])
    @patch("rpi.lib.notifications.NOTIFICATION_SERVICE_ENABLED", True)
    def test_returns_slack_when_configured(self):
        notifier = get_notifier()
        assert isinstance(notifier, SlackNotifier)

    @patch("rpi.lib.notifications.NOTIFICATION_BACKENDS", ["gmail", "slack"])
    @patch("rpi.lib.notifications.NOTIFICATION_SERVICE_ENABLED", True)
    def test_returns_composite_when_multiple_backends(self):
        notifier = get_notifier()
        assert isinstance(notifier, CompositeNotifier)
        assert len(notifier._notifiers) == 2

    @patch("rpi.lib.notifications.NOTIFICATION_SERVICE_ENABLED", False)
    def test_returns_noop_when_disabled(self):
        notifier = get_notifier()
        assert isinstance(notifier, NoOpNotifier)

    @patch("rpi.lib.notifications.NOTIFICATION_BACKENDS", ["unknown"])
    @patch("rpi.lib.notifications.NOTIFICATION_SERVICE_ENABLED", True)
    def test_returns_noop_for_unknown_backend(self):
        notifier = get_notifier()
        assert isinstance(notifier, NoOpNotifier)
