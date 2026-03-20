"""Tests for analytics processing modules."""

import pytest

from custom_components.ovo_energy_au.analytics.hourly import process_hourly_data
from custom_components.ovo_energy_au.analytics.insights import compute_insights
from custom_components.ovo_energy_au.analytics.interval import process_interval_data
from custom_components.ovo_energy_au.models import PlanConfig


class TestIntervalProcessing:
    """Test interval data processing."""

    def test_empty_data_returns_defaults(self):
        result = process_interval_data(None)
        assert result["daily"] == {}
        assert result["monthly"] == {}
        assert result["yearly"] == {}
        assert result["last_3_days"] == []

    def test_empty_dict_returns_defaults(self):
        result = process_interval_data({})
        assert result["daily"] == {}

    def test_processes_daily_solar(self, sample_interval_data):
        result = process_interval_data(sample_interval_data)
        # Latest solar entry should be March 19
        assert result["daily"]["solar_consumption"] == 14.2

    def test_processes_daily_grid(self, sample_interval_data):
        result = process_interval_data(sample_interval_data)
        assert result["daily"]["grid_consumption"] == 9.1

    def test_builds_daily_map(self, sample_interval_data):
        result = process_interval_data(sample_interval_data)
        all_daily = result.get("all_daily_entries", [])
        assert len(all_daily) >= 2
        # Sorted newest first
        assert all_daily[0]["date"] >= all_daily[-1]["date"]

    def test_extracts_rate_breakdown(self, sample_interval_data):
        result = process_interval_data(sample_interval_data)
        # Daily rate breakdown from the latest export entry
        rb = result["daily"].get("rate_breakdown", {})
        assert "OTHER" in rb
        assert rb["OTHER"]["consumption"] == 9.1

    def test_monthly_solar_consumption(self, sample_interval_data):
        result = process_interval_data(sample_interval_data)
        assert result["monthly"]["solar_consumption"] == 280.0

    def test_all_time_aggregation(self, sample_interval_data):
        result = process_interval_data(sample_interval_data)
        all_time = result["all_time"]
        assert all_time["solar_consumption"] == 280.0
        assert all_time["months_included"] == 1


    def test_daily_accumulates_credit_and_debit(self):
        """Test that days with both CREDIT and DEBIT entries accumulate correctly."""
        data = {
            "daily": {
                "solar": [
                    {"periodFrom": "2026-03-19T00:00:00Z", "consumption": 10.0,
                     "charge": {"value": -1.0, "type": "CREDIT"}},
                ],
                "export": [
                    # DEBIT entry (grid consumption)
                    {"periodFrom": "2026-03-19T00:00:00Z", "consumption": 5.0,
                     "charge": {"value": 1.50, "type": "DEBIT"}, "rates": []},
                    # CREDIT entry (return to grid) - same day
                    {"periodFrom": "2026-03-19T00:00:00Z", "consumption": 3.0,
                     "charge": {"value": -0.30, "type": "CREDIT"}, "rates": []},
                ],
            },
        }
        result = process_interval_data(data)
        all_daily = result.get("all_daily_entries", [])
        assert len(all_daily) == 1
        day = all_daily[0]
        # Both should be populated, not one zeroed out
        assert day["grid_consumption"] == 5.0
        assert day["return_to_grid"] == 3.0

    def test_period_latest_accumulates_both_types(self):
        """Test _process_period_latest accumulates CREDIT and DEBIT."""
        data = {
            "daily": {
                "solar": [],
                "export": [
                    {"periodFrom": "2026-03-19T00:00:00Z", "consumption": 8.0,
                     "charge": {"value": 2.40, "type": "DEBIT"}},
                    {"periodFrom": "2026-03-19T00:00:00Z", "consumption": 4.0,
                     "charge": {"value": -0.40, "type": "CREDIT"}},
                ],
            },
        }
        result = process_interval_data(data)
        assert result["daily"]["grid_consumption"] == 8.0
        assert result["daily"]["return_to_grid"] == 4.0


class TestHourlyProcessing:
    """Test hourly data processing."""

    def test_empty_data(self, plan_config):
        result = process_hourly_data(None, plan_config)
        assert result["solar_total"] == 0
        assert result["grid_total"] == 0

    def test_separates_solar_and_grid(self, sample_hourly_data, plan_config):
        result = process_hourly_data(sample_hourly_data, plan_config)
        assert len(result["solar_entries"]) == 24
        assert result["solar_total"] > 0

    def test_grid_entries_populated(self, sample_hourly_data, plan_config):
        result = process_hourly_data(sample_hourly_data, plan_config)
        assert len(result["grid_entries"]) == 24
        assert result["grid_total"] > 0

    def test_tou_breakdown_populated(self, sample_hourly_data, plan_config):
        result = process_hourly_data(sample_hourly_data, plan_config)
        tou = result["time_of_use"]
        assert "ev_offpeak" in tou
        assert "free" in tou
        assert "other" in tou

    def test_ev_usage_tracked(self, sample_hourly_data, plan_config):
        result = process_hourly_data(sample_hourly_data, plan_config)
        # EV entries are hours 0-5 (charge_type=EV_OFFPEAK)
        ev = result["ev_usage"]
        assert ev["consumption"] > 0

    def test_heatmap_generated(self, sample_hourly_data, plan_config):
        result = process_hourly_data(sample_hourly_data, plan_config)
        assert len(result["hourly_heatmap"]) > 0


class TestInsights:
    """Test analytics insights computation."""

    def test_no_crash_on_empty(self):
        processed = {}
        compute_insights(processed)
        # Should not add any keys without data
        assert "week_comparison" not in processed

    def test_self_sufficiency(self, sample_interval_data):
        processed = process_interval_data(sample_interval_data)
        compute_insights(processed)
        ss = processed.get("self_sufficiency")
        assert ss is not None
        assert 0 <= ss["score"] <= 100
        assert ss["period_days"] > 0
        # Verify self-consumed = solar - exported (not raw solar)
        assert "self_consumed_kwh" in ss
        assert "exported_kwh" in ss
        assert ss["self_consumed_kwh"] <= ss["solar_kwh"]

    def test_cost_per_kwh(self, sample_interval_data):
        processed = process_interval_data(sample_interval_data)
        compute_insights(processed)
        cpk = processed.get("cost_per_kwh")
        assert cpk is not None
        assert cpk["total_consumption"] > 0

    def test_high_usage_days(self, sample_interval_data):
        processed = process_interval_data(sample_interval_data)
        compute_insights(processed)
        high = processed.get("high_usage_days")
        assert high is not None
        assert len(high) > 0
        # Should be sorted descending by consumption
        if len(high) > 1:
            assert high[0]["total_consumption"] >= high[1]["total_consumption"]

    def test_return_to_grid_analysis(self, sample_interval_data):
        processed = process_interval_data(sample_interval_data)
        compute_insights(processed)
        rtg = processed.get("return_to_grid_analysis")
        assert rtg is not None
        assert "export_kwh" in rtg
        assert "purchase_rate_per_kwh" in rtg
