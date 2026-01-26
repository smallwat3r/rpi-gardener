"""Tests for the DHT22 polling module."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rpi.dht.models import Measure, Reading
from rpi.dht.polling import DHTPollingService
from rpi.lib.config import Unit


class TestDHTPollingServiceAudit:
    """Tests for DHT22 sensor boundary validation during audit."""

    @pytest.fixture
    def service(self, mock_sensor, mock_publisher, alert_tracker):
        """Create a DHTPollingService instance for testing."""
        return DHTPollingService(mock_sensor, mock_publisher, alert_tracker)

    @pytest.mark.asyncio
    async def test_valid_reading_passes(self, service, sample_reading):
        with patch("rpi.dht.polling.audit_reading", new_callable=AsyncMock):
            result = await service.audit(sample_reading)
            assert result is True

    @pytest.mark.asyncio
    async def test_temperature_below_min_fails(self, service, frozen_time):
        reading = Reading(
            temperature=Measure(-50.0, Unit.CELSIUS),
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )

        result = await service.audit(reading)
        assert result is False

    @pytest.mark.asyncio
    async def test_temperature_above_max_fails(self, service, frozen_time):
        reading = Reading(
            temperature=Measure(85.0, Unit.CELSIUS),
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )

        result = await service.audit(reading)
        assert result is False

    @pytest.mark.asyncio
    async def test_humidity_below_min_fails(self, service, frozen_time):
        reading = Reading(
            temperature=Measure(22.0, Unit.CELSIUS),
            humidity=Measure(-5.0, Unit.PERCENT),
            recording_time=frozen_time,
        )

        result = await service.audit(reading)
        assert result is False

    @pytest.mark.asyncio
    async def test_humidity_above_max_fails(self, service, frozen_time):
        reading = Reading(
            temperature=Measure(22.0, Unit.CELSIUS),
            humidity=Measure(105.0, Unit.PERCENT),
            recording_time=frozen_time,
        )

        result = await service.audit(reading)
        assert result is False

    @pytest.mark.asyncio
    async def test_boundary_values_valid(self, service, frozen_time):
        """Readings at exact boundaries should be valid."""
        with patch("rpi.dht.polling.audit_reading", new_callable=AsyncMock):
            # Min temperature boundary
            reading = Reading(
                temperature=Measure(-40.0, Unit.CELSIUS),
                humidity=Measure(50.0, Unit.PERCENT),
                recording_time=frozen_time,
            )
            assert await service.audit(reading) is True

            # Max temperature boundary
            reading = Reading(
                temperature=Measure(80.0, Unit.CELSIUS),
                humidity=Measure(50.0, Unit.PERCENT),
                recording_time=frozen_time,
            )
            assert await service.audit(reading) is True

            # Humidity boundaries
            reading = Reading(
                temperature=Measure(22.0, Unit.CELSIUS),
                humidity=Measure(0.0, Unit.PERCENT),
                recording_time=frozen_time,
            )
            assert await service.audit(reading) is True

            reading = Reading(
                temperature=Measure(22.0, Unit.CELSIUS),
                humidity=Measure(100.0, Unit.PERCENT),
                recording_time=frozen_time,
            )
            assert await service.audit(reading) is True


class TestDHTPollingServicePoll:
    """Tests for polling the DHT22 sensor."""

    @pytest.fixture
    def service(self, mock_sensor, mock_publisher, alert_tracker):
        """Create a DHTPollingService instance for testing."""
        return DHTPollingService(mock_sensor, mock_publisher, alert_tracker)

    @pytest.mark.asyncio
    @patch("asyncio.to_thread")
    async def test_poll_updates_reading(
        self, mock_to_thread, service, frozen_time
    ):
        with patch("rpi.dht.polling.datetime") as mock_dt:
            mock_dt.now.return_value = frozen_time

            # Mock to_thread to return the values directly
            mock_to_thread.side_effect = [25.5, 60.0]

            result = await service.poll()

            assert result.temperature.value == 25.5
            assert result.humidity.value == 60.0
            assert result.recording_time == frozen_time


class TestDHTPollingServicePersist:
    """Tests for persisting readings to the database."""

    @pytest.fixture
    def service(self, mock_sensor, mock_publisher, alert_tracker):
        """Create a DHTPollingService instance for testing."""
        return DHTPollingService(mock_sensor, mock_publisher, alert_tracker)

    @pytest.mark.asyncio
    async def test_persist_inserts_reading(self, service, sample_reading):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_publisher = MagicMock()

        @asynccontextmanager
        async def mock_get_db():
            yield mock_db

        service._publisher = mock_publisher

        with patch("rpi.dht.polling.get_db", mock_get_db):
            await service.persist(sample_reading)

        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params[0] == sample_reading.temperature.value
        assert params[1] == sample_reading.humidity.value
        assert params[2] == int(sample_reading.recording_time.timestamp())
        mock_publisher.publish.assert_called_once()


class TestDHTPollingServiceErrorHandling:
    """Tests for error handling in the polling service."""

    @pytest.fixture
    def service(self, mock_sensor, mock_publisher, alert_tracker):
        """Create a DHTPollingService instance for testing."""
        return DHTPollingService(mock_sensor, mock_publisher, alert_tracker)

    def test_on_poll_error_handles_runtime_error(self, service, caplog):
        """RuntimeError from DHT should be logged as debug."""
        error = RuntimeError("Checksum failure")
        service.on_poll_error(error)
        # Should not raise, just log

    def test_on_poll_error_handles_other_errors(self, service, caplog):
        """Other errors should be handled by parent class."""
        error = ValueError("Some other error")
        service.on_poll_error(error)
        # Should not raise, just log
