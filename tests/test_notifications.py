"""Tests for the notification system."""

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rpi.lib.alerts import AlertEvent, Namespace
from rpi.lib.notifications import (
    CompositeNotifier,
    GmailNotifier,
    NoOpNotifier,
    SlackNotifier,
    format_alert_message,
    get_notifier,
    get_sensor_label,
)


def make_alert_event(
    sensor_name="temperature",
    value=30.5,
    unit="c",
    threshold=25,
    recording_time=None,
    namespace=Namespace.DHT,
    is_resolved=False,
):
    """Create an AlertEvent for testing."""
    from datetime import datetime

    if recording_time is None:
        recording_time = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
    return AlertEvent(
        namespace=namespace,
        sensor_name=sensor_name,
        value=value,
        unit=unit,
        threshold=threshold if not is_resolved else None,
        recording_time=recording_time,
        is_resolved=is_resolved,
    )


class TestAlertEvent:
    """Tests for the AlertEvent dataclass."""

    def test_alert_event_creation(self, frozen_time):
        event = make_alert_event(
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
        assert event.namespace == Namespace.DHT
        assert event.is_resolved is False

    def test_resolved_event_creation(self, frozen_time):
        event = make_alert_event(
            sensor_name="temperature",
            value=22.0,
            unit="c",
            recording_time=frozen_time,
            is_resolved=True,
        )

        assert event.sensor_name == "temperature"
        assert event.value == 22.0
        assert event.threshold is None
        assert event.is_resolved is True

    def test_format_alert_message(self, frozen_time):
        event = make_alert_event(
            sensor_name="humidity",
            value=75.0,
            unit="%",
            threshold=65,
            recording_time=frozen_time,
        )

        message = format_alert_message(event)

        assert "Humidity" in message
        assert "too humid" in message
        assert "75.0%" in message
        assert "65%" in message
        assert "12:00:00" in message

    def test_format_resolved_message(self, frozen_time):
        event = make_alert_event(
            sensor_name="humidity",
            value=50.0,
            unit="%",
            recording_time=frozen_time,
            is_resolved=True,
        )

        message = format_alert_message(event)

        assert "Humidity" in message
        assert "back to normal" in message
        assert "50.0%" in message
        assert "12:00:00" in message

    def test_label_from_sensor_labels(self, frozen_time):
        event = make_alert_event(
            sensor_name="temperature",
            value=30.0,
            unit="c",
            threshold=25,
            recording_time=frozen_time,
        )
        assert get_sensor_label(event.sensor_name) == "Temperature"

    def test_label_fallback(self, frozen_time):
        event = make_alert_event(
            sensor_name="custom-sensor",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )
        assert get_sensor_label(event.sensor_name) == "Custom Sensor"


class TestGmailNotifier:
    """Tests for the Gmail notification backend."""

    @pytest.mark.asyncio
    @patch("rpi.lib.notifications.SMTP")
    @patch("rpi.lib.notifications.ssl.create_default_context")
    async def test_successful_send(self, mock_ssl, mock_smtp, frozen_time):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        event = make_alert_event(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = GmailNotifier()
        await notifier.send(event)

        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("rpi.lib.notifications.SMTP")
    @patch("rpi.lib.notifications.ssl.create_default_context")
    async def test_retry_on_network_error(
        self, mock_ssl, mock_smtp, mock_sleep, frozen_time
    ):
        mock_server = MagicMock()
        mock_server.send_message.side_effect = [OSError("Network error"), None]
        mock_smtp.return_value.__enter__.return_value = mock_server

        event = make_alert_event(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = GmailNotifier()
        await notifier.send(event)

        assert mock_server.send_message.call_count == 2

    @pytest.mark.asyncio
    @patch("rpi.lib.notifications.SMTP")
    @patch("rpi.lib.notifications.ssl.create_default_context")
    async def test_no_retry_on_non_network_error(
        self, mock_ssl, mock_smtp, frozen_time
    ):
        mock_server = MagicMock()
        mock_server.send_message.side_effect = ValueError("Bad data")
        mock_smtp.return_value.__enter__.return_value = mock_server

        event = make_alert_event(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = GmailNotifier()
        await notifier.send(event)

        assert mock_server.send_message.call_count == 1

    def test_build_email(self, frozen_time):
        event = make_alert_event(
            sensor_name="humidity",
            value=75.0,
            unit="%",
            threshold=65,
            recording_time=frozen_time,
        )

        notifier = GmailNotifier()
        message = notifier._build_email(
            "Test Subject", format_alert_message(event)
        )

        assert message["Subject"] == "Test Subject"
        assert format_alert_message(event) in message.get_content()

    @pytest.mark.asyncio
    @patch("rpi.lib.notifications.SMTP")
    @patch("rpi.lib.notifications.ssl.create_default_context")
    async def test_send_resolved(self, mock_ssl, mock_smtp, frozen_time):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        event = make_alert_event(
            sensor_name="temperature",
            value=22.0,
            unit="c",
            recording_time=frozen_time,
            is_resolved=True,
        )

        notifier = GmailNotifier()
        await notifier.send(event)

        mock_server.send_message.assert_called_once()


class TestSlackNotifier:
    """Tests for the Slack notification backend."""

    @pytest.mark.asyncio
    @patch("rpi.lib.notifications.requests.post")
    async def test_successful_send(self, mock_post, frozen_time):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        event = make_alert_event(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = SlackNotifier()
        await notifier.send(event)

        mock_post.assert_called_once()

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("rpi.lib.notifications.requests.post")
    async def test_retry_on_network_error(
        self, mock_post, mock_sleep, frozen_time
    ):
        mock_success = MagicMock()
        mock_success.raise_for_status = MagicMock()
        mock_post.side_effect = [
            OSError("Network error"),
            mock_success,
        ]

        event = make_alert_event(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = SlackNotifier()
        await notifier.send(event)

        assert mock_post.call_count == 2

    @pytest.mark.asyncio
    @patch("rpi.lib.notifications.requests.post")
    async def test_no_retry_on_non_network_error(self, mock_post, frozen_time):
        mock_post.side_effect = ValueError("Bad data")

        event = make_alert_event(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = SlackNotifier()
        await notifier.send(event)

        assert mock_post.call_count == 1

    def test_build_payload(self, frozen_time):
        notifier = SlackNotifier()
        fields = [
            {"type": "mrkdwn", "text": "*Current:*\n75.0%"},
            {"type": "mrkdwn", "text": "*Threshold:*\n65%"},
        ]
        payload = notifier._build_payload("Humidity Alert", fields, "12:00:00")

        assert payload["text"] == "Humidity Alert"
        assert payload["blocks"][0]["type"] == "header"
        assert "Humidity Alert" in payload["blocks"][0]["text"]["text"]
        # Check fields section
        result_fields = payload["blocks"][1]["fields"]
        assert "75.0%" in result_fields[0]["text"]
        assert "65%" in result_fields[1]["text"]

    @pytest.mark.asyncio
    @patch("rpi.lib.notifications.requests.post")
    async def test_send_resolved(self, mock_post, frozen_time):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        event = make_alert_event(
            sensor_name="temperature",
            value=22.0,
            unit="c",
            recording_time=frozen_time,
            is_resolved=True,
        )

        notifier = SlackNotifier()
        await notifier.send(event)

        mock_post.assert_called_once()


class TestCompositeNotifier:
    """Tests for the composite notification backend."""

    @pytest.mark.asyncio
    async def test_sends_to_all_backends(self, frozen_time):
        mock_notifier1 = MagicMock()
        mock_notifier1.send = AsyncMock()
        mock_notifier2 = MagicMock()
        mock_notifier2.send = AsyncMock()

        event = make_alert_event(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        composite = CompositeNotifier([mock_notifier1, mock_notifier2])
        await composite.send(event)

        mock_notifier1.send.assert_called_once_with(event)
        mock_notifier2.send.assert_called_once_with(event)


class TestNoOpNotifier:
    """Tests for the no-op notification backend."""

    @pytest.mark.asyncio
    async def test_send_logs_only(self, frozen_time, caplog):
        event = make_alert_event(
            sensor_name="test",
            value=50.0,
            unit="%",
            threshold=30,
            recording_time=frozen_time,
        )

        notifier = NoOpNotifier()
        await notifier.send(event)

        assert "disabled" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_send_resolved_logs_only(self, frozen_time, caplog):
        event = make_alert_event(
            sensor_name="temperature",
            value=22.0,
            unit="c",
            recording_time=frozen_time,
            is_resolved=True,
        )

        notifier = NoOpNotifier()
        await notifier.send(event)

        assert "disabled" in caplog.text.lower()


class TestGetNotifier:
    """Tests for the notifier factory function."""

    @pytest.mark.asyncio
    async def test_returns_gmail_when_configured(self):
        async def mock_effective():
            mock = MagicMock()
            mock.enabled = True
            mock.backends = ["gmail"]
            return mock

        with patch(
            "rpi.lib.notifications.get_effective_notifications", mock_effective
        ):
            notifier = await get_notifier()
            assert isinstance(notifier, GmailNotifier)

    @pytest.mark.asyncio
    async def test_returns_slack_when_configured(self):
        async def mock_effective():
            mock = MagicMock()
            mock.enabled = True
            mock.backends = ["slack"]
            return mock

        with patch(
            "rpi.lib.notifications.get_effective_notifications", mock_effective
        ):
            notifier = await get_notifier()
            assert isinstance(notifier, SlackNotifier)

    @pytest.mark.asyncio
    async def test_returns_composite_when_multiple_backends(self):
        async def mock_effective():
            mock = MagicMock()
            mock.enabled = True
            mock.backends = ["gmail", "slack"]
            return mock

        with patch(
            "rpi.lib.notifications.get_effective_notifications", mock_effective
        ):
            notifier = await get_notifier()
            assert isinstance(notifier, CompositeNotifier)

    @pytest.mark.asyncio
    async def test_returns_noop_when_disabled(self):
        async def mock_effective():
            mock = MagicMock()
            mock.enabled = False
            return mock

        with patch(
            "rpi.lib.notifications.get_effective_notifications", mock_effective
        ):
            notifier = await get_notifier()
            assert isinstance(notifier, NoOpNotifier)

    @pytest.mark.asyncio
    async def test_returns_noop_for_unknown_backend(self):
        async def mock_effective():
            mock = MagicMock()
            mock.enabled = True
            mock.backends = ["unknown"]
            return mock

        with patch(
            "rpi.lib.notifications.get_effective_notifications", mock_effective
        ):
            notifier = await get_notifier()
            assert isinstance(notifier, NoOpNotifier)
