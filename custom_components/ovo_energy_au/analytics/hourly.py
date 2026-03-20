"""Hourly data processing and time-of-use breakdown."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ..models import PlanConfig

_LOGGER = logging.getLogger(__name__)

AU_TIMEZONE = ZoneInfo("Australia/Sydney")

# Map API charge types to internal TOU period keys
_CHARGE_TYPE_TO_PERIOD = {
    "PEAK": "peak",
    "OFF_PEAK": "off_peak",
    "SHOULDER": "shoulder",
    "DEBIT": "shoulder",
    "FREE": "free",
    "FREE_3": "free",
    "EV_OFFPEAK": "ev_offpeak",
    "OTHER": "other",
}


def process_hourly_data(data: dict | None, plan_config: PlanConfig) -> dict:
    """Process hourly data into entries, totals, TOU breakdown, and tracking.

    Unlike interval data, we keep ALL hourly entries for graphing.
    """
    if data is None:
        data = {}

    processed = {
        "solar_entries": [],
        "grid_entries": [],
        "return_to_grid_entries": [],
        "solar_total": 0.0,
        "grid_total": 0.0,
        "return_to_grid_total": 0.0,
    }

    solar_raw = data.get("solar", []) or []
    export_raw = data.get("export", []) or []

    # Separate entries - store only needed fields (Bug 5 fix)
    for entry in solar_raw:
        processed["solar_entries"].append({
            "periodFrom": entry.get("periodFrom"),
            "periodTo": entry.get("periodTo"),
            "consumption": entry.get("consumption", 0) or 0,
            "charge": entry.get("charge", {}),
        })
        processed["solar_total"] += entry.get("consumption", 0) or 0

    for entry in export_raw:
        charge_info = entry.get("charge", {})
        charge_type = charge_info.get("type", "DEBIT")
        consumption = entry.get("consumption", 0) or 0
        slim_entry = {
            "periodFrom": entry.get("periodFrom"),
            "periodTo": entry.get("periodTo"),
            "consumption": consumption,
            "charge": charge_info,
            "rates": entry.get("rates"),
        }
        if charge_type == "CREDIT":
            processed["return_to_grid_entries"].append(slim_entry)
            processed["return_to_grid_total"] += consumption
        else:
            processed["grid_entries"].append(slim_entry)
            processed["grid_total"] += consumption

    # Aggregate by rate type
    processed["hourly_rates_breakdown"] = _aggregate_hourly_rates(processed["grid_entries"])

    # Build timeline for analytics
    timeline = _build_timeline(processed)

    # TOU breakdown
    processed["time_of_use"] = _compute_tou_breakdown(timeline)

    # Free and EV usage tracking (Bug 1 fix: use AEST instead of UTC)
    now_aest = datetime.now(AU_TIMEZONE)
    _add_usage_tracking(processed, timeline, plan_config, now_aest)

    # Heatmap
    processed["hourly_heatmap"] = _compute_heatmap(timeline)

    # Peak 4-hour window
    processed["peak_4hour_window"] = _find_peak_window(timeline)

    return processed


def _aggregate_hourly_rates(grid_entries: list[dict]) -> dict:
    """Aggregate grid entries by rate type."""
    aggregation = {}
    for entry in grid_entries:
        rates_list = entry.get("rates") or []
        if not isinstance(rates_list, list):
            continue
        period_from = entry.get("periodFrom", "")
        for rate_entry in rates_list:
            if not isinstance(rate_entry, dict):
                continue
            rate_type = rate_entry.get("type")
            if not rate_type:
                continue

            if rate_type not in aggregation:
                aggregation[rate_type] = {"consumption": 0, "charge": 0, "hours": 0, "_seen_hours": set()}

            charge_obj = rate_entry.get("charge", {})
            charge_value = abs(charge_obj.get("value", 0)) if isinstance(charge_obj, dict) else 0

            aggregation[rate_type]["consumption"] += rate_entry.get("consumption", 0)
            aggregation[rate_type]["charge"] += charge_value
            if period_from not in aggregation[rate_type]["_seen_hours"]:
                aggregation[rate_type]["_seen_hours"].add(period_from)
                aggregation[rate_type]["hours"] += 1

    for rt in aggregation:
        aggregation[rt]["consumption"] = round(aggregation[rt]["consumption"], 2)
        aggregation[rt]["charge"] = round(aggregation[rt]["charge"], 2)
        del aggregation[rt]["_seen_hours"]  # Clean up internal tracking

    return aggregation


def _build_timeline(processed: dict) -> list[dict]:
    """Build a unified hourly timeline from solar and grid entries."""
    timeline = []

    for entry in processed["solar_entries"]:
        ts = _parse_timestamp(entry.get("periodFrom", ""))
        if ts is None:
            continue
        charge_info = entry.get("charge", {})
        timeline.append({
            "timestamp": ts,
            "hour": ts.hour,
            "consumption": entry.get("consumption", 0),
            "type": "solar",
            "charge_type": charge_info.get("type", "DEBIT"),
            "charge_value": charge_info.get("value", 0),
        })

    for entry in processed["grid_entries"]:
        ts = _parse_timestamp(entry.get("periodFrom", ""))
        if ts is None:
            continue
        rates_list = entry.get("rates") or []
        charge_info = entry.get("charge", {})

        if rates_list and isinstance(rates_list, list):
            for rate_entry in rates_list:
                if not isinstance(rate_entry, dict):
                    continue
                rate_charge = rate_entry.get("charge", {})
                timeline.append({
                    "timestamp": ts,
                    "hour": ts.hour,
                    "consumption": rate_entry.get("consumption", 0) or 0,
                    "type": "grid",
                    "charge_type": rate_entry.get("type", "OTHER"),
                    "charge_value": rate_charge.get("value", 0) if isinstance(rate_charge, dict) else 0,
                })
        else:
            timeline.append({
                "timestamp": ts,
                "hour": ts.hour,
                "consumption": entry.get("consumption", 0) or 0,
                "type": "grid",
                "charge_type": charge_info.get("type", "DEBIT"),
                "charge_value": charge_info.get("value", 0),
            })

    timeline.sort(key=lambda x: x["timestamp"])
    return timeline


def _parse_timestamp(period_from: str) -> datetime | None:
    """Parse an ISO timestamp string and convert to Australian Eastern time.

    This ensures hour-of-day calculations (heatmap, peak window, TOU)
    use local Australian hours, not UTC.
    """
    if not period_from:
        return None
    try:
        ts = datetime.fromisoformat(period_from.replace("Z", "+00:00"))
        return ts.astimezone(AU_TIMEZONE)
    except (ValueError, TypeError):
        return None


def _compute_tou_breakdown(timeline: list[dict]) -> dict:
    """Compute time-of-use consumption/cost breakdown."""
    tou = {
        period: {"consumption": 0.0, "cost": 0.0, "hours": 0}
        for period in ["peak", "shoulder", "off_peak", "ev_offpeak", "free", "other"]
    }

    for entry in timeline:
        charge_type = entry.get("charge_type", "DEBIT")
        consumption = entry["consumption"]
        charge_value = abs(entry.get("charge_value", 0))

        if charge_type == "CREDIT" or consumption <= 0:
            continue

        period = _CHARGE_TYPE_TO_PERIOD.get(charge_type, "other")
        tou[period]["consumption"] += consumption
        tou[period]["cost"] += charge_value
        tou[period]["hours"] += 1

    for period in tou:
        tou[period]["consumption"] = round(tou[period]["consumption"], 2)
        tou[period]["cost"] = round(tou[period]["cost"], 2)

    return tou


def _add_usage_tracking(
    processed: dict,
    timeline: list[dict],
    plan_config: PlanConfig,
    now_aest: datetime,
) -> None:
    """Add free usage and EV usage tracking (MTD, weekly, yearly)."""
    current_month = now_aest.month
    current_year = now_aest.year
    seven_days_ago = now_aest - timedelta(days=7)

    free_mtd = {"consumption": 0.0, "cost_saved": 0.0, "hours": 0}
    ev_mtd = {"consumption": 0.0, "cost": 0.0, "cost_saved": 0.0, "hours": 0}
    ev_weekly = {"consumption": 0.0, "cost": 0.0, "cost_saved": 0.0, "hours": 0}
    ev_yearly = {"consumption": 0.0, "cost": 0.0, "cost_saved": 0.0, "hours": 0}

    for entry in timeline:
        # Convert entry timestamps to AEST before comparing (Bug 1 fix)
        ts = entry["timestamp"].astimezone(AU_TIMEZONE) if entry["timestamp"].tzinfo else entry["timestamp"]
        charge_type = entry.get("charge_type", "DEBIT")
        consumption = entry["consumption"]
        charge_value = abs(entry.get("charge_value", 0))
        is_current_month = ts.month == current_month and ts.year == current_year

        # Free usage (MTD)
        if charge_type in ["FREE", "FREE_3"] and is_current_month:
            free_mtd["consumption"] += consumption
            free_mtd["hours"] += 1
            free_mtd["cost_saved"] += consumption * plan_config.shoulder_rate

        # EV tracking
        if charge_type == "EV_OFFPEAK":
            savings = consumption * (plan_config.off_peak_rate - plan_config.ev_rate)
            if is_current_month:
                ev_mtd["consumption"] += consumption
                ev_mtd["cost"] += charge_value
                ev_mtd["hours"] += 1
                ev_mtd["cost_saved"] += savings
            if ts >= seven_days_ago:
                ev_weekly["consumption"] += consumption
                ev_weekly["cost"] += charge_value
                ev_weekly["hours"] += 1
                ev_weekly["cost_saved"] += savings
            if ts.year == current_year:
                ev_yearly["consumption"] += consumption
                ev_yearly["cost"] += charge_value
                ev_yearly["hours"] += 1
                ev_yearly["cost_saved"] += savings

    def _round_tracking(d: dict) -> None:
        for k in d:
            if isinstance(d[k], float):
                d[k] = round(d[k], 2)

    _round_tracking(free_mtd)
    _round_tracking(ev_mtd)
    _round_tracking(ev_weekly)
    _round_tracking(ev_yearly)

    processed["free_usage"] = free_mtd
    processed["ev_usage"] = ev_mtd
    processed["ev_usage_weekly"] = ev_weekly
    processed["ev_usage_monthly"] = ev_mtd.copy()  # Bug 4 fix: avoid aliasing same dict
    processed["ev_usage_yearly"] = ev_yearly


def _compute_heatmap(timeline: list[dict]) -> dict:
    """Compute day-of-week x hour average consumption heatmap."""
    # First aggregate consumption per unique (date, hour) to avoid double-counting (Bug 3 fix)
    hour_totals = {}  # {(date_str, hour): consumption}
    for entry in timeline:
        ts = entry["timestamp"]
        date_str = ts.strftime("%Y-%m-%d")
        hour = ts.hour
        key = (date_str, hour)
        hour_totals[key] = hour_totals.get(key, 0) + entry["consumption"]

    # Now build day-of-week averages from deduplicated hourly totals
    buckets = {}  # {day_name: {hour: {total, count}}}
    for (date_str, hour), consumption in hour_totals.items():
        day_name = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")
        if day_name not in buckets:
            buckets[day_name] = {}
        if hour not in buckets[day_name]:
            buckets[day_name][hour] = {"total": 0.0, "count": 0}
        buckets[day_name][hour]["total"] += consumption
        buckets[day_name][hour]["count"] += 1

    return {
        day: {
            hour: round(data["total"] / data["count"], 2) if data["count"] > 0 else 0
            for hour, data in hours.items()
        }
        for day, hours in buckets.items()
    }


def _find_peak_window(timeline: list[dict]) -> dict | None:
    """Find the peak 4-hour consumption window."""
    if len(timeline) < 4:
        return None

    # Pre-aggregate by hour to avoid double-counting (Bug 2 fix)
    hourly_totals = {}
    for entry in timeline:
        ts = entry["timestamp"]
        hour_key = ts.strftime("%Y-%m-%d %H")
        if hour_key not in hourly_totals:
            hourly_totals[hour_key] = {
                "timestamp": ts.replace(minute=0, second=0, microsecond=0),
                "hour": ts.hour,
                "consumption": 0,
            }
        hourly_totals[hour_key]["consumption"] += entry["consumption"]

    sorted_hours = sorted(hourly_totals.values(), key=lambda x: x["timestamp"])

    if len(sorted_hours) < 4:
        return None

    max_consumption = 0
    peak_window = None
    for i in range(len(sorted_hours) - 3):
        window = sorted_hours[i:i + 4]
        total = sum(h["consumption"] for h in window)
        if total > max_consumption:
            max_consumption = total
            peak_window = {
                "start_time": window[0]["timestamp"].strftime("%Y-%m-%d %H:%M"),
                "end_time": window[3]["timestamp"].strftime("%Y-%m-%d %H:%M"),
                "start_hour": window[0]["hour"],
                "total_consumption": round(total, 2),
                "hourly_breakdown": [
                    {"hour": h["timestamp"].strftime("%H:%M"), "consumption": round(h["consumption"], 2)}
                    for h in window
                ],
            }
    return peak_window
