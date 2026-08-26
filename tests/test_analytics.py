"""Tests for analytics processing modules."""


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
        # conftest freezes dt_util.now() at 2026-03-20 to match the March
        # fixture data — ev_usage is month-to-date relative to that clock
        result = process_hourly_data(sample_hourly_data, plan_config)
        # EV entries are hours 0-5 (charge_type=EV_OFFPEAK)
        ev = result["ev_usage"]
        assert ev["consumption"] > 0

    def test_heatmap_generated(self, sample_hourly_data, plan_config):
        result = process_hourly_data(sample_hourly_data, plan_config)
        assert len(result["hourly_heatmap"]) > 0


class TestSplitOtherByWindow:
    """Test re-bucketing OTHER usage into peak/off-peak (issue #63/#74).

    These use REALISTIC hourly data: the OVO hourly API returns ``charge: null``
    and ``rates: null`` for every entry (no per-hour rate/cost signal), so the
    split must work off hour-of-day alone. The earlier fixture fabricated
    ``charge.type == "OTHER"`` and cost values that the API never sends, which is
    why the broken v4.2.1 build passed tests yet read 0 against real data.
    """

    @staticmethod
    def _make_data(hours_consumption):
        """Build realistic hourly export data (charge=null, rates=null).

        hours_consumption: list of (aest_hour, consumption).
        Timestamps are June (AEST, UTC+10): local hour H = UTC hour H-10.
        """
        export = []
        for hour, consumption in hours_consumption:
            utc_hour = (hour - 10) % 24
            # Pick the UTC date so the local date stays 2026-06-10
            day = 9 if hour < 10 else 10
            export.append({
                "periodFrom": f"2026-06-{day:02d}T{utc_hour:02d}:00:00Z",
                "consumption": consumption,
                "charge": None,  # real hourly API
                "rates": None,   # real hourly API
            })
        return {"solar": [], "export": export}

    def test_no_window_leaves_other_untouched(self):
        plan = PlanConfig(plan_type="free_3")
        data = self._make_data([(16, 2.0), (3, 1.0)])
        result = process_hourly_data(data, plan)
        tou = result["time_of_use"]
        assert tou["other"]["consumption"] == 3.0
        assert tou["peak"]["consumption"] == 0.0
        assert tou["off_peak"]["consumption"] == 0.0

    def test_window_splits_other_into_peak_and_off_peak(self):
        """Regression for #74: real (rate-less) hourly consumption must split."""
        plan = PlanConfig(plan_type="free_3", peak_start_hour=15, peak_end_hour=21)
        data = self._make_data([
            (16, 2.0),  # inside window -> peak
            (20, 1.5),  # inside window -> peak
            (3, 1.0),   # outside -> off_peak
            (22, 0.5),  # outside (end-exclusive boundary passed) -> off_peak
        ])
        result = process_hourly_data(data, plan)
        tou = result["time_of_use"]
        assert tou["peak"]["consumption"] == 3.5
        assert tou["off_peak"]["consumption"] == 1.5
        assert tou["other"]["consumption"] == 0.0
        # Cost is unavailable from hourly data (charge is null) -> always 0.
        assert tou["peak"]["cost"] == 0.0
        assert tou["off_peak"]["cost"] == 0.0

    def test_window_boundaries_are_start_inclusive_end_exclusive(self):
        plan = PlanConfig(plan_type="free_3", peak_start_hour=15, peak_end_hour=21)
        data = self._make_data([(15, 1.0), (21, 1.0)])
        result = process_hourly_data(data, plan)
        tou = result["time_of_use"]
        assert tou["peak"]["consumption"] == 1.0
        assert tou["off_peak"]["consumption"] == 1.0

    def test_overnight_window(self):
        plan = PlanConfig(plan_type="free_3", peak_start_hour=21, peak_end_hour=7)
        data = self._make_data([
            (23, 1.0),  # in overnight window -> peak
            (3, 2.0),   # in overnight window -> peak
            (12, 1.5),  # outside -> off_peak
        ])
        result = process_hourly_data(data, plan)
        tou = result["time_of_use"]
        assert tou["peak"]["consumption"] == 3.0
        assert tou["off_peak"]["consumption"] == 1.5

    def test_solar_entries_excluded_from_tou(self):
        """Solar generation is not grid usage and must not inflate the split."""
        plan = PlanConfig(plan_type="free_3", peak_start_hour=15, peak_end_hour=21)
        data = {
            "solar": [{"periodFrom": "2026-06-10T06:00:00Z", "consumption": 9.0,
                       "charge": None}],
            "export": [{"periodFrom": "2026-06-10T06:00:00Z", "consumption": 2.0,
                        "charge": None, "rates": None}],  # local 16:00 -> peak
        }
        result = process_hourly_data(data, plan)
        tou = result["time_of_use"]
        assert tou["peak"]["consumption"] == 2.0
        total = sum(b["consumption"] for b in tou.values())
        assert total == 2.0  # solar 9.0 not counted anywhere in TOU

    def test_rates_present_classified_by_type_not_window(self):
        """If the API ever DOES return hourly rates, entries are classified by
        rate type and the window split only touches unclassified OTHER usage."""
        plan = PlanConfig(plan_type="free_3", peak_start_hour=15, peak_end_hour=21)
        data = {
            "solar": [],
            "export": [
                {"periodFrom": "2026-06-10T06:00:00Z", "consumption": 2.0, "charge": None,
                 "rates": [{"type": "OFF_PEAK", "consumption": 2.0,
                            "charge": {"value": 0.36, "type": "DEBIT"}}]},
                {"periodFrom": "2026-06-10T08:00:00Z", "consumption": 1.0, "charge": None,
                 "rates": [{"type": "FREE_3", "consumption": 1.0,
                            "charge": {"value": 0.0, "type": "DEBIT"}}]},
            ],
        }
        result = process_hourly_data(data, plan)
        tou = result["time_of_use"]
        assert tou["off_peak"]["consumption"] == 2.0
        assert tou["free"]["consumption"] == 1.0
        assert tou["peak"]["consumption"] == 0.0


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

    def test_high_usage_uses_household_consumption_not_total_solar_generation(self):
        processed = {
            "all_daily_entries": [
                {
                    "date": "2026-03-19",
                    "day_name": "Thursday",
                    "solar_consumption": 20,
                    "return_to_grid": 18,
                    "return_to_grid_charge": -0.54,
                    "grid_consumption": 1,
                    "grid_charge": 0.40,
                },
                {
                    "date": "2026-03-18",
                    "day_name": "Wednesday",
                    "solar_consumption": 2,
                    "return_to_grid": 0,
                    "return_to_grid_charge": 0,
                    "grid_consumption": 6,
                    "grid_charge": 2.40,
                },
            ]
        }

        compute_insights(processed)

        high = processed["high_usage_days"]
        assert high[0]["date"] == "2026-03-18"
        assert high[0]["total_consumption"] == 8
        sunny = next(day for day in high if day["date"] == "2026-03-19")
        assert sunny["self_consumed_solar"] == 2
        assert sunny["total_consumption"] == 3
        assert sunny["net_usage_cost"] == -0.14

    def test_comparison_costs_are_grid_charge_less_export_credit(self):
        entries = []
        for index in range(14):
            entries.append({
                "date": f"2026-03-{19 - index:02d}",
                "solar_consumption": 10,
                "solar_charge": -99,
                "return_to_grid": 4,
                "return_to_grid_charge": -2 if index < 7 else -1,
                "grid_consumption": 5,
                "grid_charge": 5 if index < 7 else 4,
            })
        processed = {"all_daily_entries": entries}

        compute_insights(processed)

        comparison = processed["week_comparison"]
        assert comparison["this_week_cost"] == 21
        assert comparison["last_week_cost"] == 21
        assert comparison["cost_basis"] == "grid_charges_less_export_credits"
        assert processed["weekday_analysis"]["cost_basis"] == (
            "grid_charges_less_export_credits_excludes_supply_charge"
        )

    def test_obsolete_monthly_projection_is_not_computed(self, sample_interval_data):
        processed = process_interval_data(sample_interval_data)

        compute_insights(processed)

        assert "monthly_projection" not in processed

    def test_return_to_grid_analysis(self, sample_interval_data):
        processed = process_interval_data(sample_interval_data)
        compute_insights(processed)
        rtg = processed.get("return_to_grid_analysis")
        assert rtg is not None
        assert "export_kwh" in rtg
        assert "purchase_rate_per_kwh" in rtg
