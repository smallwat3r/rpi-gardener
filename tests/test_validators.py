"""Tests for server request validators."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from rpi.server.validators import (
    DEFAULT_HOURS,
    MAX_HOURS,
    MIN_HOURS,
    HoursQuery,
)


class TestHoursQuery:
    """Tests for HoursQuery validation."""

    def test_default_hours(self):
        query = HoursQuery()
        assert query.hours == DEFAULT_HOURS

    def test_valid_hours(self, frozen_time):
        with patch("rpi.server.validators.datetime") as mock_dt:
            mock_dt.now.return_value = frozen_time
            query = HoursQuery(hours=12)

            assert query.hours == 12
            assert query.from_time == frozen_time - timedelta(hours=12)

    def test_min_boundary(self):
        query = HoursQuery(hours=MIN_HOURS)
        assert query.hours == MIN_HOURS

    def test_max_boundary(self):
        query = HoursQuery(hours=MAX_HOURS)
        assert query.hours == MAX_HOURS

    def test_below_min_raises(self):
        with pytest.raises(ValidationError):
            HoursQuery(hours=0)

    def test_above_max_raises(self):
        with pytest.raises(ValidationError):
            HoursQuery(hours=MAX_HOURS + 1)


class TestHoursQueryFromParams:
    """Tests for HoursQuery.from_params()."""

    def test_default_when_empty(self):
        query = HoursQuery.from_params({})
        assert query.hours == DEFAULT_HOURS

    def test_default_when_none(self):
        query = HoursQuery.from_params(None)
        assert query.hours == DEFAULT_HOURS

    def test_valid_hours_parsed(self, frozen_time):
        with patch("rpi.server.validators.datetime") as mock_dt:
            mock_dt.now.return_value = frozen_time
            query = HoursQuery.from_params({"hours": "12"})

            assert query.hours == 12
            assert query.from_time == frozen_time - timedelta(hours=12)

    def test_non_integer_raises(self):
        with pytest.raises(ValueError, match="must be an integer"):
            HoursQuery.from_params({"hours": "abc"})

    def test_float_string_raises(self):
        with pytest.raises(ValueError, match="must be an integer"):
            HoursQuery.from_params({"hours": "3.5"})

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="must be an integer"):
            HoursQuery.from_params({"hours": ""})

    def test_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            HoursQuery.from_params({"hours": str(MAX_HOURS + 1)})
