"""Data models for OVO Energy Australia integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict


class RateBreakdownEntry(TypedDict, total=False):
    """A single rate type's breakdown data."""

    consumption: float
    charge: float
    percent: float
    available: bool


class DailyEntry(TypedDict, total=False):
    """A single day's energy data."""

    date: str
    day_name: str
    day: int
    month: int
    year: int
    solar_consumption: float
    solar_charge: float
    grid_consumption: float
    grid_charge: float
    return_to_grid: float
    return_to_grid_charge: float
    periodFrom: str
    periodTo: str
    grid_rates_kwh: dict[str, float]
    grid_rates_aud: dict[str, float]


class PeriodData(TypedDict, total=False):
    """Processed data for a time period (daily/monthly/yearly)."""

    solar_consumption: float
    solar_charge: float
    solar_latest: dict
    grid_consumption: float
    grid_charge: float
    grid_latest: dict
    return_to_grid: float
    return_to_grid_charge: float
    rate_breakdown: dict[str, RateBreakdownEntry]
    solar_daily_breakdown: list[dict]
    grid_daily_breakdown: list[dict]
    return_daily_breakdown: list[dict]
    solar_daily_avg: float
    solar_daily_max: float
    solar_charge_daily_avg: float


class TOUPeriodData(TypedDict):
    """Time-of-use period data."""

    consumption: float
    cost: float
    hours: int


class EVUsageData(TypedDict):
    """EV usage tracking data."""

    consumption: float
    cost: float
    cost_saved: float
    hours: int


class WeekComparisonData(TypedDict, total=False):
    """Week-over-week comparison."""

    this_week_solar: float
    last_week_solar: float
    solar_change: float
    solar_change_pct: float
    this_week_grid: float
    last_week_grid: float
    grid_change: float
    grid_change_pct: float
    this_week_cost: float
    last_week_cost: float
    cost_change: float
    cost_change_pct: float


class SelfSufficiencyData(TypedDict):
    """Solar self-sufficiency metrics."""

    score: float
    solar_kwh: float
    grid_kwh: float
    total_kwh: float
    period_days: int


class MonthlyProjectionData(TypedDict):
    """Monthly cost projection."""

    projected_total: float
    current_mtd: float
    projected_remaining: float
    daily_average: float
    days_elapsed: int
    days_remaining: int
    days_in_month: int


class ReturnToGridAnalysis(TypedDict):
    """Return-to-grid value analysis."""

    export_kwh: float
    export_credit: float
    export_rate_per_kwh: float
    purchase_rate_per_kwh: float
    rate_difference: float
    potential_savings: float
    actual_credit: float
    opportunity_cost: float


@dataclass
class PlanConfig:
    """User's energy plan configuration."""

    plan_type: str = "basic"
    peak_rate: float = 0.35
    shoulder_rate: float = 0.25
    off_peak_rate: float = 0.18
    ev_rate: float = 0.06
    flat_rate: float = 0.28

    @classmethod
    def from_dict(cls, data: dict) -> PlanConfig:
        """Create from a dictionary."""
        return cls(
            plan_type=data.get("plan_type", "basic"),
            peak_rate=data.get("peak_rate", 0.35),
            shoulder_rate=data.get("shoulder_rate", 0.25),
            off_peak_rate=data.get("off_peak_rate", 0.18),
            ev_rate=data.get("ev_rate", 0.06),
            flat_rate=data.get("flat_rate", 0.28),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "plan_type": self.plan_type,
            "peak_rate": self.peak_rate,
            "shoulder_rate": self.shoulder_rate,
            "off_peak_rate": self.off_peak_rate,
            "ev_rate": self.ev_rate,
            "flat_rate": self.flat_rate,
        }
