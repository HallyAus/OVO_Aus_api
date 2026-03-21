"""Tests for historically problematic edge cases.

These cover null fields, missing keys, flat-rate users, and other
scenarios that have caused issues in production.
"""

import pytest

from custom_components.ovo_energy_au.analytics.interval import process_interval_data
from custom_components.ovo_energy_au.analytics.hourly import process_hourly_data
from custom_components.ovo_energy_au.analytics.insights import compute_insights
from custom_components.ovo_energy_au.models import PlanConfig
from custom_components.ovo_energy_au.sensors.definitions import get_rate_value


class TestNullSolarAndExport:
    """Null or missing solar/export fields in interval data."""

    def test_interval_data_with_null_solar(self):
        """solar key exists but its value is null."""
        data = {
            "daily": {
                "solar": None,
                "export": [
                    {"periodFrom": "2026-03-19T00:00:00Z", "consumption": 5.0,
                     "charge": {"value": 1.50, "type": "DEBIT"}, "rates": []},
                ],
            },
        }
        result = process_interval_data(data)
        # Solar should gracefully be absent/zero
        assert result["daily"].get("solar_consumption", 0) in (0, 0.0, None)
        # Grid should still be populated
        assert result["daily"]["grid_consumption"] == 5.0

    def test_interval_data_with_null_export(self):
        """export key exists but is null."""
        data = {
            "daily": {
                "solar": [
                    {"periodFrom": "2026-03-19T00:00:00Z", "consumption": 10.0,
                     "charge": {"value": -1.0, "type": "CREDIT"}},
                ],
                "export": None,
            },
        }
        result = process_interval_data(data)
        assert result["daily"]["solar_consumption"] == 10.0
        assert result["daily"].get("grid_consumption", 0) in (0, 0.0, None)

    def test_interval_data_with_null_rates(self):
        """export entry has rates: null instead of a list."""
        data = {
            "daily": {
                "solar": [],
                "export": [
                    {"periodFrom": "2026-03-19T00:00:00Z", "consumption": 7.0,
                     "charge": {"value": 2.10, "type": "DEBIT"},
                     "rates": None},
                ],
            },
        }
        result = process_interval_data(data)
        assert result["daily"]["grid_consumption"] == 7.0
        # rate_breakdown should be empty or not crash
        rb = result["daily"].get("rate_breakdown", {})
        assert isinstance(rb, dict)

    def test_interval_data_with_missing_keys(self):
        """No solar key at all in daily dict."""
        data = {
            "daily": {
                "export": [
                    {"periodFrom": "2026-03-19T00:00:00Z", "consumption": 6.0,
                     "charge": {"value": 1.80, "type": "DEBIT"}, "rates": []},
                ],
            },
        }
        result = process_interval_data(data)
        assert result["daily"].get("solar_consumption", 0) in (0, 0.0, None)
        assert result["daily"]["grid_consumption"] == 6.0


class TestHourlyNullData:
    """Null hourly data edge case."""

    def test_hourly_data_completely_null(self):
        """Passing None as hourly data should return safe defaults."""
        pc = PlanConfig()
        result = process_hourly_data(None, pc)
        assert result["solar_total"] == 0
        assert result["grid_total"] == 0
        assert result.get("solar_entries", []) == []
        assert result.get("grid_entries", []) == []


class TestDailyEntryNoCharge:
    """Daily entry missing the charge object entirely."""

    def test_daily_entry_with_no_charge_object(self):
        """Entry without a 'charge' key should not crash."""
        data = {
            "daily": {
                "solar": [
                    {"periodFrom": "2026-03-19T00:00:00Z", "consumption": 8.0},
                ],
                "export": [
                    {"periodFrom": "2026-03-19T00:00:00Z", "consumption": 4.0,
                     "rates": []},
                ],
            },
        }
        result = process_interval_data(data)
        # Should still process consumption even without charge
        assert result["daily"]["solar_consumption"] == 8.0


class TestRateBreakdownMalformed:
    """Malformed rate breakdown entries."""

    def test_rate_breakdown_with_malformed_entries(self):
        """Rate entries missing expected fields should not crash."""
        data = {
            "daily": {
                "solar": [],
                "export": [
                    {"periodFrom": "2026-03-19T00:00:00Z", "consumption": 10.0,
                     "charge": {"value": 3.00, "type": "DEBIT"},
                     "rates": [
                         # Missing 'consumption' and 'charge'
                         {"type": "PEAK", "percentOfTotal": 0.5},
                         # Missing 'type'
                         {"consumption": 2.0, "charge": {"value": 0.5, "type": "DEBIT"}},
                         # Completely empty
                         {},
                     ]},
                ],
            },
        }
        # Should not raise
        result = process_interval_data(data)
        assert result["daily"]["grid_consumption"] == 10.0


class TestNoSolarUser:
    """User with no solar system - only grid data."""

    def test_no_solar_user(self):
        """Data with empty solar lists should still process grid correctly."""
        data = {
            "daily": {
                "solar": [],
                "export": [
                    {"periodFrom": "2026-03-19T00:00:00Z", "consumption": 20.0,
                     "charge": {"value": 6.00, "type": "DEBIT"},
                     "rates": [
                         {"type": "OTHER", "consumption": 20.0,
                          "charge": {"value": 6.00, "type": "DEBIT"},
                          "percentOfTotal": 1.0},
                     ]},
                ],
            },
            "monthly": {
                "solar": [],
                "export": [
                    {"periodFrom": "2026-03-01T00:00:00Z", "consumption": 400.0,
                     "charge": {"value": 120.0, "type": "DEBIT"}},
                ],
            },
        }
        result = process_interval_data(data)
        assert result["daily"]["grid_consumption"] == 20.0
        assert result["daily"].get("solar_consumption", 0) in (0, 0.0, None)
        assert result["monthly"]["grid_consumption"] == 400.0

        # Insights should also work without solar
        compute_insights(result)
        ss = result.get("self_sufficiency")
        if ss is not None:
            assert ss["solar_kwh"] == 0 or ss["score"] == 0


class TestFlatRatePlanUser:
    """User on a flat rate plan with no TOU breakdown."""

    def test_flat_rate_plan_user(self):
        """Only DEBIT entries with no rate types except OTHER/DEBIT."""
        data = {
            "daily": {
                "solar": [],
                "export": [
                    {"periodFrom": "2026-03-19T00:00:00Z", "consumption": 15.0,
                     "charge": {"value": 4.20, "type": "DEBIT"},
                     "rates": [
                         {"type": "OTHER", "consumption": 15.0,
                          "charge": {"value": 4.20, "type": "DEBIT"},
                          "percentOfTotal": 1.0},
                     ]},
                ],
            },
        }
        result = process_interval_data(data)
        assert result["daily"]["grid_consumption"] == 15.0
        rb = result["daily"].get("rate_breakdown", {})
        # Should only have OTHER
        if rb:
            assert "OTHER" in rb
            assert "PEAK" not in rb or not rb.get("PEAK", {}).get("available", False)


class TestPercentOfTotalAlreadyPercentage:
    """percentOfTotal > 1.0 - edge case where API returns percentage as whole number."""

    def test_percentOfTotal_already_percentage(self):
        """Should handle percentOfTotal > 1.0 without crashing."""
        data = {
            "daily": {
                "solar": [],
                "export": [
                    {"periodFrom": "2026-03-19T00:00:00Z", "consumption": 10.0,
                     "charge": {"value": 3.00, "type": "DEBIT"},
                     "rates": [
                         {"type": "PEAK", "consumption": 4.0,
                          "charge": {"value": 1.40, "type": "DEBIT"},
                          "percentOfTotal": 40.0},
                         {"type": "OFFPEAK", "consumption": 6.0,
                          "charge": {"value": 1.60, "type": "DEBIT"},
                          "percentOfTotal": 60.0},
                     ]},
                ],
            },
        }
        # Should not raise
        result = process_interval_data(data)
        assert result["daily"]["grid_consumption"] == 10.0
        rb = result["daily"].get("rate_breakdown", {})
        if rb and "PEAK" in rb:
            # The percent value should be stored (possibly as-is or normalized)
            # Main assertion: it didn't crash
            assert rb["PEAK"]["consumption"] == 4.0


class TestNullChargeInHourlyData:
    """Test that charge: null (not missing) is handled correctly.

    This is the #1 recurring crash in the integration's history.
    The API returns charge: null for hourly data, but .get("charge", {})
    returns None (not {}) when the key exists with null value.
    """

    def test_hourly_data_with_null_charge(self, plan_config):
        """Test processing hourly data where charge is null on all entries."""
        from custom_components.ovo_energy_au.analytics.hourly import process_hourly_data

        data = {
            "solar": [
                {
                    "periodFrom": "2026-03-19T20:00:00.000Z",
                    "periodTo": "2026-03-19T21:00:00.000Z",
                    "consumption": 0.608,
                    "readType": "ACTUAL",
                    "charge": None,  # This is the key: null, not missing!
                },
            ],
            "export": [
                {
                    "periodFrom": "2026-03-19T20:00:00.000Z",
                    "periodTo": "2026-03-19T21:00:00.000Z",
                    "consumption": 0.003,
                    "readType": "ACTUAL",
                    "charge": None,  # null charge
                    "rates": None,   # null rates
                },
            ],
        }

        # Should not crash
        result = process_hourly_data(data, plan_config)

        assert result["solar_total"] == 0.608
        assert result["grid_total"] == 0.003
        assert len(result["solar_entries"]) == 1
        assert len(result["grid_entries"]) == 1

    def test_interval_data_with_null_charge(self):
        """Test interval processing with null charge values."""
        from custom_components.ovo_energy_au.analytics.interval import process_interval_data

        data = {
            "daily": {
                "solar": [
                    {
                        "periodFrom": "2026-03-19T00:00:00Z",
                        "consumption": 10.0,
                        "charge": None,  # null charge
                    },
                ],
                "export": [
                    {
                        "periodFrom": "2026-03-19T00:00:00Z",
                        "consumption": 5.0,
                        "charge": None,  # null charge
                        "rates": None,
                    },
                ],
            },
        }

        # Should not crash
        result = process_interval_data(data)
        assert result["daily"]["solar_consumption"] == 10.0
        # With null charge, type defaults to DEBIT, so goes to grid
        assert result["daily"]["grid_consumption"] == 5.0
