"""Tests for the DHT22 polling module."""
from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rpi.dht.models import Measure, Reading, State, Unit
from rpi.dht.polling import DHTPollingService, OutsideDHT22Bounds


class TestDHTPollingServiceAudit:
    """Tests for DHT22 sensor boundary validation during audit."""

    @pytest.fixture
    def service(self):
        """Create a DHTPollingService instance for testing."""
        with patch("rpi.dht.polling.init_db"), \
             patch("rpi.dht.polling.start_worker"), \
             patch("rpi.dht.polling.display"):
            svc = DHTPollingService()
            return svc

    @pytest.mark.asyncio
    async def test_valid_reading_passes(self, service, sample_reading):
        with patch("rpi.dht.polling.audit_reading"):
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
        with patch("rpi.dht.polling.audit_reading"):
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
    def service(self):
        """Create a DHTPollingService instance for testing."""
        with patch("rpi.dht.polling.init_db"), \
             patch("rpi.dht.polling.start_worker"), \
             patch("rpi.dht.polling.display"):
            svc = DHTPollingService()
            return svc

    @pytest.mark.asyncio
    @patch("rpi.dht.polling.display")
    @patch("rpi.dht.polling.utcnow")
    @patch("asyncio.to_thread")
    async def test_poll_updates_reading(self, mock_to_thread, mock_time, mock_display, service, frozen_time):
        mock_time.return_value = frozen_time

        mock_dht = MagicMock()
        mock_dht.temperature = 25.5
        mock_dht.humidity = 60.0
        service._dht = mock_dht

        # Mock to_thread to return the values directly
        mock_to_thread.side_effect = [25.5, 60.0]

        result = await service.poll()

        assert result.temperature.value == 25.5
        assert result.humidity.value == 60.0
        assert result.recording_time == frozen_time
        mock_display.render_reading.assert_called_once()

    @pytest.mark.asyncio
    async def test_poll_returns_none_without_dht(self, service):
        """Poll should return None if DHT is not initialized."""
        service._dht = None
        result = await service.poll()
        assert result is None


class TestDHTPollingServicePersist:
    """Tests for persisting readings to the database."""

    @pytest.fixture
    def service(self):
        """Create a DHTPollingService instance for testing."""
        with patch("rpi.dht.polling.init_db"), \
             patch("rpi.dht.polling.start_worker"), \
             patch("rpi.dht.polling.display"):
            svc = DHTPollingService()
            return svc

    @pytest.mark.asyncio
    async def test_persist_inserts_reading(self, service, sample_reading):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()

        @asynccontextmanager
        async def mock_get_db():
            yield mock_db

        with patch("rpi.dht.polling.get_db", mock_get_db):
            await service.persist(sample_reading)

        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params[0] == sample_reading.temperature.value
        assert params[1] == sample_reading.humidity.value
        assert params[2] == sample_reading.recording_time


class TestDHTPollingServiceClearOldRecords:
    """Tests for clearing old database records."""

    @pytest.fixture
    def service(self):
        """Create a DHTPollingService instance for testing."""
        with patch("rpi.dht.polling.init_db"), \
             patch("rpi.dht.polling.start_worker"), \
             patch("rpi.dht.polling.display"):
            svc = DHTPollingService()
            return svc

    @pytest.mark.asyncio
    @patch("rpi.lib.polling.utcnow")
    async def test_clear_old_records_deletes_old_data(self, mock_time, service, frozen_time):
        mock_time.return_value = frozen_time
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()

        @asynccontextmanager
        async def mock_get_db():
            yield mock_db

        with patch("rpi.dht.polling.get_db", mock_get_db):
            await service.clear_old_records()

        # Should delete from both tables
        assert mock_db.execute.call_count == 2

        # Check cutoff date (3 days retention by default)
        first_call = mock_db.execute.call_args_list[0]
        cutoff = first_call[0][1][0]
        expected_cutoff = frozen_time - timedelta(days=3)
        assert cutoff == expected_cutoff


class TestDHTPollingServiceErrorHandling:
    """Tests for error handling in the polling service."""

    @pytest.fixture
    def service(self):
        """Create a DHTPollingService instance for testing."""
        with patch("rpi.dht.polling.init_db"), \
             patch("rpi.dht.polling.start_worker"), \
             patch("rpi.dht.polling.display"):
            svc = DHTPollingService()
            return svc

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
