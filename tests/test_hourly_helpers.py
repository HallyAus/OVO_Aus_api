"""Tests for hourly data helper functions in sensors/base.py."""

import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from custom_components.ovo_energy_au.sensors.base import (
    AU_TIMEZONE,
    get_hourly_data_for_date,
    get_yesterday_hourly_data,
    parse_entry_timestamp,
)


class TestParseEntryTimestamp:
    """Test the parse_entry_timestamp helper."""

    def test_parse_entry_timestamp_utc(self):
        """UTC timestamp ending with Z should be converted to AU timezone."""
        result = parse_entry_timestamp("2026-03-19T02:00:00Z")
        assert result is not None
        assert result.tzinfo == AU_TIMEZONE
        # March 19 02:00 UTC = March 19 13:00 AEDT (UTC+11 during DST)
        assert result.hour == 13
        assert result.day == 19

    def test_parse_entry_timestamp_with_offset(self):
        """Explicit offset timestamp should be handled correctly."""
        result = parse_entry_timestamp("2026-03-19T12:00:00+05:00")
        assert result is not None
        assert result.tzinfo == AU_TIMEZONE
        # 12:00+05:00 = 07:00 UTC = 18:00 AEDT (UTC+11)
        assert result.hour == 18

    def test_parse_entry_timestamp_empty_returns_none(self):
        """Empty string should return None."""
        assert parse_entry_timestamp("") is None

    def test_parse_entry_timestamp_none_returns_none(self):
        """None input should return None."""
        assert parse_entry_timestamp(None) is None

    def test_parse_entry_timestamp_invalid_returns_none(self):
        """Garbage input should return None, not raise."""
        assert parse_entry_timestamp("not-a-timestamp") is None
        assert parse_entry_timestamp("2026-13-45T99:99:99Z") is None


class TestGetHourlyDataForDate:
    """Test filtering hourly data to a specific date."""

    def _make_data(self, entries):
        """Wrap entries in the expected nested structure."""
        return {"hourly": {"solar_entries": entries}}

    def test_get_hourly_data_for_date_filters_correctly(self):
        """Should only include entries matching the target date."""
        entries = [
            {"periodFrom": "2026-03-19T00:00:00Z", "consumption": 1.0,
             "charge": {"value": 0.10, "type": "DEBIT"}},
            {"periodFrom": "2026-03-19T06:00:00Z", "consumption": 2.5,
             "charge": {"value": 0.25, "type": "DEBIT"}},
            {"periodFrom": "2026-03-20T00:00:00Z", "consumption": 3.0,
             "charge": {"value": 0.30, "type": "DEBIT"}},
        ]
        data = self._make_data(entries)
        # March 19 00:00 UTC = March 19 11:00 AEDT
        # March 19 06:00 UTC = March 19 17:00 AEDT
        # March 20 00:00 UTC = March 20 11:00 AEDT
        target = date(2026, 3, 19)
        result = get_hourly_data_for_date(data, "solar_entries", target)

        assert result["state"] == 3.5  # 1.0 + 2.5
        assert len(result["hourly_data"]) == 2

    def test_get_hourly_data_for_date_empty_data(self):
        """None or empty data should return zeroed result."""
        result = get_hourly_data_for_date(None, "solar_entries", date(2026, 3, 19))
        assert result["state"] == 0.0
        assert result["hourly_data"] == []

        result2 = get_hourly_data_for_date({}, "solar_entries", date(2026, 3, 19))
        assert result2["state"] == 0.0
        assert result2["hourly_data"] == []

    def test_get_hourly_data_for_date_wrong_date_returns_empty(self):
        """Entries on a different date should be excluded entirely."""
        entries = [
            {"periodFrom": "2026-03-18T10:00:00Z", "consumption": 5.0,
             "charge": {"value": 0.50, "type": "DEBIT"}},
        ]
        data = self._make_data(entries)
        # March 18 10:00 UTC = March 18 21:00 AEDT
        target = date(2026, 3, 19)
        result = get_hourly_data_for_date(data, "solar_entries", target)
        assert result["state"] == 0.0
        assert result["hourly_data"] == []

    def test_hourly_data_sorted_by_hour(self):
        """Returned hourly_data should be sorted by hour ascending."""
        entries = [
            {"periodFrom": "2026-03-19T08:00:00Z", "consumption": 2.0,
             "charge": {"value": 0.20, "type": "DEBIT"}},
            {"periodFrom": "2026-03-19T02:00:00Z", "consumption": 1.0,
             "charge": {"value": 0.10, "type": "DEBIT"}},
        ]
        data = self._make_data(entries)
        target = date(2026, 3, 19)
        result = get_hourly_data_for_date(data, "solar_entries", target)
        hours = [h["hour"] for h in result["hourly_data"]]
        assert hours == sorted(hours)

    def test_hourly_data_handles_null_consumption(self):
        """Entry with consumption=None should be treated as 0."""
        entries = [
            {"periodFrom": "2026-03-19T02:00:00Z", "consumption": None,
             "charge": {"value": 0.0, "type": "DEBIT"}},
        ]
        data = self._make_data(entries)
        target = date(2026, 3, 19)
        result = get_hourly_data_for_date(data, "solar_entries", target)
        assert result["state"] == 0.0
        assert len(result["hourly_data"]) == 1
        assert result["hourly_data"][0]["value"] == 0.0


class TestGetYesterdayHourlyData:
    """Test get_yesterday_hourly_data with mocked datetime."""

    @patch("custom_components.ovo_energy_au.sensors.base.datetime")
    def test_get_yesterday_hourly_data(self, mock_datetime):
        """Should filter to yesterday's date in AU timezone."""
        # Mock datetime.now to return a known time
        mock_now = datetime(2026, 3, 20, 10, 0, 0, tzinfo=AU_TIMEZONE)
        mock_datetime.now.return_value = mock_now
        # fromisoformat must still work (delegate to real datetime)
        mock_datetime.fromisoformat = datetime.fromisoformat

        entries = [
            # March 18 in UTC -> March 19 AEDT (yesterday)
            {"periodFrom": "2026-03-18T14:00:00Z", "consumption": 1.5,
             "charge": {"value": 0.15, "type": "DEBIT"}},
            # March 19 in UTC -> March 19 AEDT (yesterday)
            {"periodFrom": "2026-03-19T02:00:00Z", "consumption": 2.0,
             "charge": {"value": 0.20, "type": "DEBIT"}},
            # March 19 in UTC -> March 20 AEDT (today, not yesterday)
            {"periodFrom": "2026-03-19T14:00:00Z", "consumption": 9.0,
             "charge": {"value": 0.90, "type": "DEBIT"}},
        ]
        data = {"hourly": {"solar_entries": entries}}

        result = get_yesterday_hourly_data(data, "solar_entries")

        # Yesterday is March 19 AEDT
        # Entry 1: March 18 14:00 UTC = March 19 01:00 AEDT -> matches
        # Entry 2: March 19 02:00 UTC = March 19 13:00 AEDT -> matches
        # Entry 3: March 19 14:00 UTC = March 20 01:00 AEDT -> does NOT match
        assert result["state"] == 3.5  # 1.5 + 2.0
        assert len(result["hourly_data"]) == 2
