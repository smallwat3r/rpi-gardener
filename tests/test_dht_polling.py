"""Tests for the DHT22 polling module."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from rpi.dht import polling
from rpi.dht.models import Measure, Reading, State, Unit
from rpi.dht.polling import (
    _OutsideDHT22Bounds,
    _audit,
    _check_dht_boundaries,
    _clear_old_records,
    _persist,
    _poll,
)


class TestCheckDhtBoundaries:
    """Tests for DHT22 sensor boundary validation."""

    def test_valid_reading_passes(self, sample_reading):
        result = _check_dht_boundaries(sample_reading)
        assert result is sample_reading

    def test_temperature_below_min_raises(self, frozen_time):
        reading = Reading(
            temperature=Measure(-50.0, Unit.CELSIUS),
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )

        with pytest.raises(_OutsideDHT22Bounds):
            _check_dht_boundaries(reading)

    def test_temperature_above_max_raises(self, frozen_time):
        reading = Reading(
            temperature=Measure(85.0, Unit.CELSIUS),
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )

        with pytest.raises(_OutsideDHT22Bounds):
            _check_dht_boundaries(reading)

    def test_humidity_below_min_raises(self, frozen_time):
        reading = Reading(
            temperature=Measure(22.0, Unit.CELSIUS),
            humidity=Measure(-5.0, Unit.PERCENT),
            recording_time=frozen_time,
        )

        with pytest.raises(_OutsideDHT22Bounds):
            _check_dht_boundaries(reading)

    def test_humidity_above_max_raises(self, frozen_time):
        reading = Reading(
            temperature=Measure(22.0, Unit.CELSIUS),
            humidity=Measure(105.0, Unit.PERCENT),
            recording_time=frozen_time,
        )

        with pytest.raises(_OutsideDHT22Bounds):
            _check_dht_boundaries(reading)

    def test_boundary_values_valid(self, frozen_time):
        """Readings at exact boundaries should be valid."""
        # Min temperature boundary
        reading = Reading(
            temperature=Measure(-40.0, Unit.CELSIUS),
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )
        assert _check_dht_boundaries(reading) is reading

        # Max temperature boundary
        reading = Reading(
            temperature=Measure(80.0, Unit.CELSIUS),
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )
        assert _check_dht_boundaries(reading) is reading

        # Humidity boundaries
        reading = Reading(
            temperature=Measure(22.0, Unit.CELSIUS),
            humidity=Measure(0.0, Unit.PERCENT),
            recording_time=frozen_time,
        )
        assert _check_dht_boundaries(reading) is reading

        reading = Reading(
            temperature=Measure(22.0, Unit.CELSIUS),
            humidity=Measure(100.0, Unit.PERCENT),
            recording_time=frozen_time,
        )
        assert _check_dht_boundaries(reading) is reading


class TestPoll:
    """Tests for polling the DHT22 sensor."""

    @patch.object(polling, "display")
    @patch.object(polling, "utcnow")
    def test_poll_updates_reading(self, mock_time, mock_display, frozen_time):
        mock_time.return_value = frozen_time

        dht = MagicMock()
        dht.temperature = 25.5
        dht.humidity = 60.0

        reading = Reading(
            temperature=Measure(0.0, Unit.CELSIUS),
            humidity=Measure(0.0, Unit.PERCENT),
            recording_time=frozen_time,
        )

        result = _poll(dht, reading)

        assert result.temperature.value == 25.5
        assert result.humidity.value == 60.0
        assert result.recording_time == frozen_time
        mock_display.render_reading.assert_called_once_with(reading)


class TestAudit:
    """Tests for the audit function."""

    @patch.object(polling, "audit_reading")
    def test_audit_calls_boundary_check_and_audit(self, mock_audit_reading, sample_reading):
        result = _audit(sample_reading)

        assert result is sample_reading
        mock_audit_reading.assert_called_once_with(sample_reading)

    @patch.object(polling, "audit_reading")
    def test_audit_propagates_boundary_error(self, mock_audit_reading, frozen_time):
        reading = Reading(
            temperature=Measure(-50.0, Unit.CELSIUS),
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )

        with pytest.raises(_OutsideDHT22Bounds):
            _audit(reading)

        mock_audit_reading.assert_not_called()


class TestPersist:
    """Tests for persisting readings to the database."""

    @patch.object(polling, "db_with_config")
    def test_persist_inserts_reading(self, mock_db_factory, sample_reading):
        mock_db = MagicMock()
        mock_db_factory.return_value.__enter__.return_value = mock_db

        _persist(sample_reading)

        mock_db.commit.assert_called_once()
        call_args = mock_db.commit.call_args
        params = call_args[0][1]
        assert params[0] == sample_reading.temperature.value
        assert params[1] == sample_reading.humidity.value
        assert params[2] == sample_reading.recording_time


class TestClearOldRecords:
    """Tests for clearing old database records."""

    @patch.object(polling, "db_with_config")
    @patch.object(polling, "utcnow")
    def test_clear_old_records_deletes_old_data(self, mock_time, mock_db_factory, frozen_time):
        mock_time.return_value = frozen_time
        mock_db = MagicMock()
        mock_db_factory.return_value.__enter__.return_value = mock_db

        _clear_old_records()

        # Should delete from both tables
        assert mock_db.commit.call_count == 2

        # Check cutoff date (3 days retention by default)
        first_call = mock_db.commit.call_args_list[0]
        cutoff = first_call[0][1][0]
        expected_cutoff = frozen_time - timedelta(days=3)
        assert cutoff == expected_cutoff


class TestSignalHandling:
    """Tests for graceful shutdown signal handling."""

    def setup_method(self):
        """Reset shutdown flag before each test."""
        polling._shutdown_requested = False

    def test_handle_shutdown_sets_flag(self):
        import signal

        polling._handle_shutdown(signal.SIGTERM, None)

        assert polling._shutdown_requested is True

    def test_handle_shutdown_sigint(self):
        import signal

        polling._handle_shutdown(signal.SIGINT, None)

        assert polling._shutdown_requested is True
