"""Advanced analytics insights derived from delayed OVO meter data."""

from __future__ import annotations

from datetime import datetime


def compute_insights(processed: dict) -> None:
    """Add all analytics insights to the processed data dict (in-place).

    Cost analytics represent grid usage charges less export credits. They do
    not include the daily supply charge and therefore are not bill forecasts.
    """
    all_daily = processed.get("all_daily_entries", [])
    if not all_daily:
        return

    _add_week_comparison(processed, all_daily)
    _add_weekday_weekend(processed, all_daily)
    _add_self_sufficiency(processed, all_daily)
    _add_high_usage_days(processed, all_daily)
    _add_cost_per_kwh(processed, all_daily)
    _add_return_to_grid_analysis(processed, all_daily)


def _sum_field(entries: list[dict], *keys: str) -> float:
    """Sum one or more fields across entries."""
    return sum(sum(_number(d.get(k)) for k in keys) for d in entries)


def _number(value) -> float:
    """Normalize nullable API numerics without accepting arbitrary strings."""
    return value if isinstance(value, (int, float)) else 0


def _self_consumed_solar(entry: dict) -> float:
    """Solar used in the home rather than exported to the grid."""
    return max(0, _number(entry.get("solar_consumption")) - _number(entry.get("return_to_grid")))


def _household_consumption(entry: dict) -> float:
    """Actual household use: grid import plus self-consumed solar."""
    return _number(entry.get("grid_consumption")) + _self_consumed_solar(entry)


def _net_usage_cost(entry: dict) -> float:
    """Grid usage charge less feed-in credit, excluding the supply charge."""
    return _number(entry.get("grid_charge")) - abs(_number(entry.get("return_to_grid_charge")))


def _sum_net_usage_cost(entries: list[dict]) -> float:
    return sum(_net_usage_cost(entry) for entry in entries)


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
    tw_cost = _sum_net_usage_cost(this_week)
    lw_cost = _sum_net_usage_cost(last_week)

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
        "cost_basis": "grid_charges_less_export_credits",
        "includes_supply_charge": False,
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
            "avg_consumption": round(sum(_household_consumption(e) for e in weekday_entries) / n, 2),
            "avg_cost": round(_sum_net_usage_cost(weekday_entries) / n, 2),
            "cost_basis": "grid_charges_less_export_credits_excludes_supply_charge",
            "days": n,
        }

    if weekend_entries:
        n = len(weekend_entries)
        processed["weekend_analysis"] = {
            "avg_solar": round(_sum_field(weekend_entries, "solar_consumption") / n, 2),
            "avg_grid": round(_sum_field(weekend_entries, "grid_consumption") / n, 2),
            "avg_consumption": round(sum(_household_consumption(e) for e in weekend_entries) / n, 2),
            "avg_cost": round(_sum_net_usage_cost(weekend_entries) / n, 2),
            "cost_basis": "grid_charges_less_export_credits_excludes_supply_charge",
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
        self_consumed_solar = _self_consumed_solar(day)
        total_consumption = _household_consumption(day)
        net_usage_cost = _net_usage_cost(day)
        days.append({
            "date": day.get("date"),
            "day_name": day.get("day_name"),
            "total_consumption": round(total_consumption, 2),
            # Keep total_cost as a compatibility alias, but state its true
            # basis explicitly for existing dashboards consuming attributes.
            "total_cost": round(net_usage_cost, 2),
            "net_usage_cost": round(net_usage_cost, 2),
            "cost_includes_supply_charge": False,
            "solar": round(_number(day.get("solar_consumption")), 2),
            "self_consumed_solar": round(self_consumed_solar, 2),
            "export": round(_number(day.get("return_to_grid")), 2),
            "grid": round(_number(day.get("grid_consumption")), 2),
        })

    processed["high_usage_days"] = sorted(
        days, key=lambda x: x["total_consumption"], reverse=True
    )[:5]


def _add_cost_per_kwh(processed: dict, all_daily: list[dict]) -> None:
    """Net usage cost and import/export rates over the last 7 days."""
    last_7 = all_daily[:7]
    total_cost = _sum_net_usage_cost(last_7)
    total_kwh = sum(_household_consumption(entry) for entry in last_7)
    grid_cost = _sum_field(last_7, "grid_charge")
    grid_kwh = _sum_field(last_7, "grid_consumption")
    export_credit = abs(_sum_field(last_7, "return_to_grid_charge"))
    export_kwh = _sum_field(last_7, "return_to_grid")

    processed["cost_per_kwh"] = {
        "overall": round(total_cost / total_kwh, 4) if total_kwh > 0 else 0,
        "grid": round(grid_cost / grid_kwh, 4) if grid_kwh > 0 else 0,
        "export": round(export_credit / export_kwh, 4) if export_kwh > 0 else 0,
        "total_cost": round(total_cost, 2),
        "total_consumption": round(total_kwh, 2),
        "cost_basis": "grid_charges_less_export_credits_excludes_supply_charge",
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
