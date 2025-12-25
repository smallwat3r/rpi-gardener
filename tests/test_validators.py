"""Tests for server request validators."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from rpi.server.validators import (
    DEFAULT_HOURS,
    MAX_HOURS,
    MIN_HOURS,
    InvalidParameter,
    parse_hours,
)


class MockParams:
    """Mock object simulating request.query_params."""

    def __init__(self, data: dict | None = None):
        self._data = data or {}

    def get(self, key: str, default=None):
        return self._data.get(key, default)


class TestParseHoursStrict:
    """Tests for parse_hours in strict mode (default)."""

    @patch("rpi.server.validators.utcnow")
    def test_default_hours_when_not_provided(self, mock_utcnow, frozen_time):
        mock_utcnow.return_value = frozen_time
        params = MockParams()

        hours, from_time = parse_hours(params)

        assert hours == DEFAULT_HOURS
        assert from_time == frozen_time - timedelta(hours=DEFAULT_HOURS)

    @patch("rpi.server.validators.utcnow")
    def test_valid_hours_parsed(self, mock_utcnow, frozen_time):
        mock_utcnow.return_value = frozen_time
        params = MockParams({"hours": "12"})

        hours, from_time = parse_hours(params)

        assert hours == 12
        assert from_time == frozen_time - timedelta(hours=12)

    @patch("rpi.server.validators.utcnow")
    def test_min_hours_boundary(self, mock_utcnow, frozen_time):
        mock_utcnow.return_value = frozen_time
        params = MockParams({"hours": str(MIN_HOURS)})

        hours, from_time = parse_hours(params)

        assert hours == MIN_HOURS

    @patch("rpi.server.validators.utcnow")
    def test_max_hours_boundary(self, mock_utcnow, frozen_time):
        mock_utcnow.return_value = frozen_time
        params = MockParams({"hours": str(MAX_HOURS)})

        hours, from_time = parse_hours(params)

        assert hours == MAX_HOURS

    def test_below_min_raises(self):
        params = MockParams({"hours": "0"})

        with pytest.raises(InvalidParameter, match=f"between {MIN_HOURS} and {MAX_HOURS}"):
            parse_hours(params)

    def test_above_max_raises(self):
        params = MockParams({"hours": "25"})

        with pytest.raises(InvalidParameter, match=f"between {MIN_HOURS} and {MAX_HOURS}"):
            parse_hours(params)

    def test_non_integer_raises(self):
        params = MockParams({"hours": "abc"})

        with pytest.raises(InvalidParameter, match="needs to be an integer"):
            parse_hours(params)

    def test_float_string_raises(self):
        params = MockParams({"hours": "3.5"})

        with pytest.raises(InvalidParameter, match="needs to be an integer"):
            parse_hours(params)

    def test_empty_string_raises(self):
        params = MockParams({"hours": ""})

        with pytest.raises(InvalidParameter, match="needs to be an integer"):
            parse_hours(params)

    def test_none_value_raises(self):
        params = MockParams({"hours": None})

        with pytest.raises(InvalidParameter, match="needs to be an integer"):
            parse_hours(params)


class TestParseHoursNonStrict:
    """Tests for parse_hours in non-strict mode."""

    @patch("rpi.server.validators.utcnow")
    def test_default_for_invalid_input(self, mock_utcnow, frozen_time):
        mock_utcnow.return_value = frozen_time
        params = MockParams({"hours": "invalid"})

        hours, from_time = parse_hours(params, strict=False)

        assert hours == DEFAULT_HOURS
        assert from_time == frozen_time - timedelta(hours=DEFAULT_HOURS)

    @patch("rpi.server.validators.utcnow")
    def test_clamp_below_min(self, mock_utcnow, frozen_time):
        mock_utcnow.return_value = frozen_time
        params = MockParams({"hours": "0"})

        hours, from_time = parse_hours(params, strict=False)

        assert hours == MIN_HOURS

    @patch("rpi.server.validators.utcnow")
    def test_clamp_above_max(self, mock_utcnow, frozen_time):
        mock_utcnow.return_value = frozen_time
        params = MockParams({"hours": "100"})

        hours, from_time = parse_hours(params, strict=False)

        assert hours == MAX_HOURS

    @patch("rpi.server.validators.utcnow")
    def test_valid_hours_unchanged(self, mock_utcnow, frozen_time):
        mock_utcnow.return_value = frozen_time
        params = MockParams({"hours": "6"})

        hours, from_time = parse_hours(params, strict=False)

        assert hours == 6

    @patch("rpi.server.validators.utcnow")
    def test_negative_clamped_to_min(self, mock_utcnow, frozen_time):
        mock_utcnow.return_value = frozen_time
        params = MockParams({"hours": "-5"})

        hours, from_time = parse_hours(params, strict=False)

        assert hours == MIN_HOURS
