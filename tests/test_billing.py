"""Tests for billing-cycle aware aggregation (issue #75).

Customers whose OVO bill doesn't start on the 1st (e.g. a 24th–23rd cycle) need
month-to-date, last-cycle and projection figures to follow their real billing
period rather than the calendar month.
"""

from datetime import date

from custom_components.ovo_energy_au.analytics.billing import (
    current_cycle_bounds,
    cycle_length_days,
    previous_cycle_bounds,
)
from custom_components.ovo_energy_au.analytics.insights import compute_insights
from custom_components.ovo_energy_au.analytics.interval import process_interval_data
from custom_components.ovo_energy_au.models import PlanConfig


class TestCurrentCycleBounds:
    """Pure date-math for the current billing cycle."""

    def test_day_one_is_calendar_month(self):
        start, nxt = current_cycle_bounds(date(2026, 7, 5), 1)
        assert start == date(2026, 7, 1)
        assert nxt == date(2026, 8, 1)

    def test_zero_and_negative_treated_as_one(self):
        # Guards against a bad stored value producing an invalid date.
        assert current_cycle_bounds(date(2026, 7, 5), 0) == (date(2026, 7, 1), date(2026, 8, 1))
        assert current_cycle_bounds(date(2026, 7, 5), -3) == (date(2026, 7, 1), date(2026, 8, 1))

    def test_mid_cycle_started_previous_month(self):
        # 24th cycle, today is the 5th -> cycle started 24th of last month.
        start, nxt = current_cycle_bounds(date(2026, 7, 5), 24)
        assert start == date(2026, 6, 24)
        assert nxt == date(2026, 7, 24)

    def test_on_cycle_start_day(self):
        start, nxt = current_cycle_bounds(date(2026, 7, 24), 24)
        assert start == date(2026, 7, 24)
        assert nxt == date(2026, 8, 24)

    def test_day_before_next_cycle(self):
        start, nxt = current_cycle_bounds(date(2026, 7, 23), 24)
        assert start == date(2026, 6, 24)
        assert nxt == date(2026, 7, 24)

    def test_year_boundary(self):
        start, nxt = current_cycle_bounds(date(2026, 1, 10), 24)
        assert start == date(2025, 12, 24)
        assert nxt == date(2026, 1, 24)

    def test_cycle_day_clamped_in_short_month(self):
        # 31st cycle in February -> clamps to the last day of Feb.
        start, nxt = current_cycle_bounds(date(2026, 2, 10), 31)
        assert start == date(2026, 1, 31)
        assert nxt == date(2026, 2, 28)


class TestPreviousCycleBounds:
    """The previous complete billing cycle."""

    def test_previous_cycle_meets_current(self):
        prev_start, prev_next = previous_cycle_bounds(date(2026, 7, 5), 24)
        cur_start, _ = current_cycle_bounds(date(2026, 7, 5), 24)
        assert prev_start == date(2026, 5, 24)
        assert prev_next == date(2026, 6, 24)
        # No gap or overlap between the two cycles.
        assert prev_next == cur_start

    def test_previous_cycle_year_boundary(self):
        prev_start, prev_next = previous_cycle_bounds(date(2026, 1, 10), 24)
        assert prev_start == date(2025, 11, 24)
        assert prev_next == date(2025, 12, 24)


class TestCycleLength:
    def test_calendar_month_length(self):
        assert cycle_length_days(date(2026, 2, 10), 1) == 28
        assert cycle_length_days(date(2026, 7, 10), 1) == 31

    def test_billing_cycle_length(self):
        # 24 Jun -> 24 Jul is 30 days.
        assert cycle_length_days(date(2026, 7, 5), 24) == 30


def _export_entry(day_iso: str, consumption: float, value: float):
    """Build one DEBIT (grid) export entry the API-processing code understands."""
    return {
        "periodFrom": f"{day_iso}T00:00:00Z",
        "periodTo": f"{day_iso}T23:59:00Z",
        "consumption": consumption,
        "readType": "ACTUAL",
        "charge": {"value": value, "type": "DEBIT"},
        "rates": [],
    }


def _cycle_test_data():
    """Daily data straddling a 24th cycle boundary.

    Clock is frozen at 2026-03-20 (see conftest). For a 24th cycle the current
    period is 2026-02-24 → 2026-03-23; the previous is 2026-01-24 → 2026-02-23.
    """
    return {
        "daily": {
            "solar": [],
            "export": [
                _export_entry("2026-02-20", 5.0, 1.50),   # prev cycle (24th) / last calendar month
                _export_entry("2026-02-25", 6.0, 1.80),   # current cycle (24th) / last calendar month
                _export_entry("2026-03-10", 7.0, 2.10),   # current cycle / current calendar month
                _export_entry("2026-03-19", 8.0, 2.40),   # current cycle / current calendar month
            ],
        },
    }


class TestCycleAwareMonthToDate:
    """process_interval_data must bucket by billing cycle when configured."""

    def test_default_is_calendar_month(self):
        result = process_interval_data(_cycle_test_data())  # billing_cycle_day defaults to 1
        mtd = result["month_to_date"]
        # Only the two March days fall in the calendar month.
        assert mtd["days"] == 2
        assert mtd["grid_consumption"] == 15.0  # 7.0 + 8.0
        # Last calendar month (Feb) holds the two February days.
        assert result["last_month"]["days"] == 2
        assert result["last_month"]["grid_consumption"] == 11.0  # 5.0 + 6.0

    def test_cycle_day_24_shifts_boundaries(self):
        result = process_interval_data(_cycle_test_data(), billing_cycle_day=24)
        mtd = result["month_to_date"]
        # Current cycle (24 Feb – 23 Mar) now also includes 25 Feb.
        assert mtd["days"] == 3
        assert mtd["grid_consumption"] == 21.0  # 6.0 + 7.0 + 8.0
        # Previous cycle (24 Jan – 23 Feb) holds only 20 Feb.
        assert result["last_month"]["days"] == 1
        assert result["last_month"]["grid_consumption"] == 5.0

    def test_monthly_projection_uses_cycle_length(self):
        result = process_interval_data(_cycle_test_data(), billing_cycle_day=24)
        compute_insights(result, billing_cycle_day=24)
        proj = result["monthly_projection"]
        # 24 Feb -> 24 Mar is 28 days (Feb 2026 has 28); 3 days elapsed.
        assert proj["days_in_month"] == 28
        assert proj["days_elapsed"] == 3
        assert proj["days_remaining"] == 25


def test_plan_config_round_trips_cycle_day():
    cfg = PlanConfig.from_dict({"billing_cycle_day": 24})
    assert cfg.billing_cycle_day == 24
    assert cfg.to_dict()["billing_cycle_day"] == 24
    # Missing / falsy values fall back to a calendar month.
    assert PlanConfig.from_dict({}).billing_cycle_day == 1
    assert PlanConfig.from_dict({"billing_cycle_day": None}).billing_cycle_day == 1
