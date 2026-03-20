"""Advanced analytics insights (week comparison, projections, etc.)."""

from __future__ import annotations

import calendar
from datetime import datetime

from ..const import AU_TIMEZONE


def compute_insights(processed: dict) -> None:
    """Add all analytics insights to the processed data dict (in-place).

    This computes: week comparison, weekday/weekend analysis, self-sufficiency,
    high usage days, cost per kWh, monthly projection, return-to-grid analysis.
    """
    all_daily = processed.get("all_daily_entries", [])
    if not all_daily:
        return

    _add_week_comparison(processed, all_daily)
    _add_weekday_weekend(processed, all_daily)
    _add_self_sufficiency(processed, all_daily)
    _add_high_usage_days(processed, all_daily)
    _add_cost_per_kwh(processed, all_daily)
    _add_monthly_projection(processed)
    _add_return_to_grid_analysis(processed, all_daily)


def _sum_field(entries: list[dict], *keys: str) -> float:
    """Sum one or more fields across entries."""
    return sum(sum(d.get(k, 0) for k in keys) for d in entries)


def _safe_pct(a: float, b: float) -> float | None:
    """Calculate percentage change, returning None if denominator is 0."""
    if b == 0:
        return None
    return round(((a - b) / b * 100), 2)


def _add_week_comparison(processed: dict, all_daily: list[dict]) -> None:
    """Week-over-week comparison (requires 14+ days)."""
    if len(all_daily) < 14:
        return

    this_week = all_daily[:7]
    last_week = all_daily[7:14]

    tw_solar = _sum_field(this_week, "solar_consumption")
    lw_solar = _sum_field(last_week, "solar_consumption")
    tw_grid = _sum_field(this_week, "grid_consumption")
    lw_grid = _sum_field(last_week, "grid_consumption")
    tw_cost = _sum_field(this_week, "solar_charge", "grid_charge")
    lw_cost = _sum_field(last_week, "solar_charge", "grid_charge")

    processed["week_comparison"] = {
        "this_week_solar": round(tw_solar, 2),
        "last_week_solar": round(lw_solar, 2),
        "solar_change": round(tw_solar - lw_solar, 2),
        "solar_change_pct": _safe_pct(tw_solar, lw_solar),
        "this_week_grid": round(tw_grid, 2),
        "last_week_grid": round(lw_grid, 2),
        "grid_change": round(tw_grid - lw_grid, 2),
        "grid_change_pct": _safe_pct(tw_grid, lw_grid),
        "this_week_cost": round(tw_cost, 2),
        "last_week_cost": round(lw_cost, 2),
        "cost_change": round(tw_cost - lw_cost, 2),
        "cost_change_pct": _safe_pct(tw_cost, lw_cost),
    }


def _add_weekday_weekend(processed: dict, all_daily: list[dict]) -> None:
    """Weekday vs weekend average analysis."""
    weekday_entries = []
    weekend_entries = []

    for entry in all_daily:
        date_str = entry.get("date", "")
        if not date_str:
            continue
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            if date_obj.weekday() < 5:
                weekday_entries.append(entry)
            else:
                weekend_entries.append(entry)
        except (ValueError, TypeError):
            continue

    if weekday_entries:
        n = len(weekday_entries)
        processed["weekday_analysis"] = {
            "avg_solar": round(_sum_field(weekday_entries, "solar_consumption") / n, 2),
            "avg_grid": round(_sum_field(weekday_entries, "grid_consumption") / n, 2),
            "avg_cost": round(_sum_field(weekday_entries, "solar_charge", "grid_charge") / n, 2),
            "days": n,
        }

    if weekend_entries:
        n = len(weekend_entries)
        processed["weekend_analysis"] = {
            "avg_solar": round(_sum_field(weekend_entries, "solar_consumption") / n, 2),
            "avg_grid": round(_sum_field(weekend_entries, "grid_consumption") / n, 2),
            "avg_cost": round(_sum_field(weekend_entries, "solar_charge", "grid_charge") / n, 2),
            "days": n,
        }


def _add_self_sufficiency(processed: dict, all_daily: list[dict]) -> None:
    """Solar self-sufficiency score over last 7 days."""
    last_7 = all_daily[:7]
    total_solar = _sum_field(last_7, "solar_consumption")
    total_grid = _sum_field(last_7, "grid_consumption")
    total_export = _sum_field(last_7, "return_to_grid")
    self_consumed_solar = max(0, total_solar - total_export)
    total_consumption = self_consumed_solar + total_grid

    processed["self_sufficiency"] = {
        "score": round((self_consumed_solar / total_consumption * 100) if total_consumption > 0 else 0, 2),
        "solar_kwh": round(total_solar, 2),
        "self_consumed_kwh": round(self_consumed_solar, 2),
        "exported_kwh": round(total_export, 2),
        "grid_kwh": round(total_grid, 2),
        "total_kwh": round(total_consumption, 2),
        "period_days": len(last_7),
    }


def _add_high_usage_days(processed: dict, all_daily: list[dict]) -> None:
    """Top 5 highest usage days in last 30 days."""
    last_30 = all_daily[:30]
    days = []
    for day in last_30:
        total_consumption = day.get("solar_consumption", 0) + day.get("grid_consumption", 0)
        total_cost = day.get("solar_charge", 0) + day.get("grid_charge", 0)
        days.append({
            "date": day.get("date"),
            "day_name": day.get("day_name"),
            "total_consumption": round(total_consumption, 2),
            "total_cost": round(total_cost, 2),
            "solar": round(day.get("solar_consumption", 0), 2),
            "grid": round(day.get("grid_consumption", 0), 2),
        })

    processed["high_usage_days"] = sorted(
        days, key=lambda x: x["total_consumption"], reverse=True
    )[:5]


def _add_cost_per_kwh(processed: dict, all_daily: list[dict]) -> None:
    """Cost per kWh tracking over last 7 days."""
    last_7 = all_daily[:7]
    total_cost = _sum_field(last_7, "solar_charge", "grid_charge")
    total_kwh = _sum_field(last_7, "solar_consumption", "grid_consumption")
    grid_cost = _sum_field(last_7, "grid_charge")
    grid_kwh = _sum_field(last_7, "grid_consumption")
    solar_cost = _sum_field(last_7, "solar_charge")
    solar_kwh = _sum_field(last_7, "solar_consumption")

    processed["cost_per_kwh"] = {
        "overall": round(total_cost / total_kwh, 4) if total_kwh > 0 else 0,
        "grid": round(grid_cost / grid_kwh, 4) if grid_kwh > 0 else 0,
        "solar": round(solar_cost / solar_kwh, 4) if solar_kwh > 0 else 0,
        "total_cost": round(total_cost, 2),
        "total_consumption": round(total_kwh, 2),
    }


def _add_monthly_projection(processed: dict) -> None:
    """Monthly cost projection from month-to-date data."""
    mtd = processed.get("month_to_date", {})
    mtd_days = mtd.get("days", 0)
    if not mtd_days:
        return

    # Sum all cost fields
    mtd_cost = (
        mtd.get("solar_charge", 0) + mtd.get("grid_charge", 0)
    )

    # Use AEST for month info (Australian integration)
    now = datetime.now(AU_TIMEZONE)
    current_month = now.month
    current_year = now.year
    days_in_month = calendar.monthrange(current_year, current_month)[1]
    days_remaining = days_in_month - mtd_days

    daily_avg = mtd_cost / mtd_days
    processed["monthly_projection"] = {
        "projected_total": round(daily_avg * days_in_month, 2),
        "current_mtd": round(mtd_cost, 2),
        "projected_remaining": round(daily_avg * days_remaining, 2),
        "daily_average": round(daily_avg, 2),
        "days_elapsed": mtd_days,
        "days_remaining": days_remaining,
        "days_in_month": days_in_month,
    }


def _add_return_to_grid_analysis(processed: dict, all_daily: list[dict]) -> None:
    """Return-to-grid value analysis over last 7 days."""
    last_7 = all_daily[:7]
    rtg_kwh = _sum_field(last_7, "return_to_grid")
    rtg_credit = _sum_field(last_7, "return_to_grid_charge")
    grid_kwh = _sum_field(last_7, "grid_consumption")
    grid_cost = _sum_field(last_7, "grid_charge")

    export_rate = abs(rtg_credit / rtg_kwh) if rtg_kwh > 0 else 0
    purchase_rate = grid_cost / grid_kwh if grid_kwh > 0 else 0

    processed["return_to_grid_analysis"] = {
        "export_kwh": round(rtg_kwh, 2),
        "export_credit": round(abs(rtg_credit), 2),
        "export_rate_per_kwh": round(export_rate, 4),
        "purchase_rate_per_kwh": round(purchase_rate, 4),
        "rate_difference": round(purchase_rate - export_rate, 4),
        "potential_savings": round(rtg_kwh * purchase_rate, 2),
        "actual_credit": round(abs(rtg_credit), 2),
        "opportunity_cost": round((rtg_kwh * purchase_rate) - abs(rtg_credit), 2),
    }
