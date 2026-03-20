"""Interval data processing (daily/monthly/yearly)."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


def process_interval_data(data: dict) -> dict:
    """Process interval data from the OVO API.

    The API returns arrays of historical data:
    - daily: individual day entries (latest = yesterday, available at 6am)
    - monthly: individual month entries (latest = current month)
    - yearly: individual year entries (latest = current year)
    """
    processed = {
        "daily": {},
        "monthly": {},
        "yearly": {},
        "last_3_days": [],
        "last_7_days": {},
        "last_month": {},
        "month_to_date": {},
        "all_time": _empty_all_time(),
    }

    if not data or not isinstance(data, dict):
        return processed

    # Process each period's latest entry
    for period in ["daily", "monthly", "yearly"]:
        period_data = data.get(period)
        if not period_data or not isinstance(period_data, dict):
            continue
        processed[period] = _process_period_latest(period, period_data)

    # Build daily map for aggregations
    daily_data = data.get("daily")
    if daily_data and isinstance(daily_data, dict):
        daily_map = _build_daily_map(daily_data)
        all_daily_entries = sorted(daily_map.values(), key=lambda x: x["date"], reverse=True)[:90]
        processed["all_daily_entries"] = all_daily_entries

        now = dt_util.now()
        _add_aggregations(processed, all_daily_entries, now)
        _add_monthly_breakdowns(processed, daily_data, now)

    # All-time aggregation from monthly data
    if "monthly" in data and isinstance(data.get("monthly"), dict):
        processed["all_time"] = _compute_all_time(data["monthly"])

    return processed


def _empty_all_time() -> dict:
    """Return empty all-time structure."""
    return {
        "rate_breakdown": {},
        "solar_consumption": 0,
        "solar_charge": 0,
        "periodFrom": None,
        "periodTo": None,
        "months_included": 0,
    }


def _process_period_latest(period: str, period_data: dict) -> dict:
    """Process the latest entry from a period (solar + export)."""
    result = {}

    # Solar data
    if "solar" in period_data and period_data["solar"]:
        latest = period_data["solar"][-1]
        result["solar_consumption"] = latest.get("consumption", 0)
        result["solar_charge"] = latest.get("charge", {}).get("value", 0)
        result["solar_latest"] = latest

    # Export data - accumulate ALL entries for the latest period, separating CREDIT vs DEBIT
    if "export" in period_data and period_data["export"]:
        entries = period_data["export"]
        latest_period = entries[-1].get("periodFrom")

        result["grid_consumption"] = 0
        result["grid_charge"] = 0
        result["return_to_grid"] = 0
        result["return_to_grid_charge"] = 0
        result["grid_latest"] = entries[-1]

        # Accumulate all entries from the latest period
        for entry in entries:
            if entry.get("periodFrom") != latest_period:
                continue
            charge_type = entry.get("charge", {}).get("type", "DEBIT")
            consumption = entry.get("consumption", 0)
            charge_value = entry.get("charge", {}).get("value", 0)
            if charge_type == "CREDIT":
                result["return_to_grid"] += consumption
                result["return_to_grid_charge"] += charge_value
            else:
                result["grid_consumption"] += consumption
                result["grid_charge"] += charge_value

        # Merge rate breakdowns from ALL entries in the latest period
        merged_rates = {}
        for entry in entries:
            if entry.get("periodFrom") != latest_period:
                continue
            for rt, rd in _extract_rate_breakdown(period, entry).items():
                if rt not in merged_rates:
                    merged_rates[rt] = {"consumption": 0, "charge": 0, "percent": 0, "available": True}
                merged_rates[rt]["consumption"] += rd.get("consumption", 0)
                merged_rates[rt]["charge"] += rd.get("charge", 0)
                merged_rates[rt]["percent"] += rd.get("percent", 0)
        result["rate_breakdown"] = merged_rates

    return result


def _extract_rate_breakdown(period: str, export_entry: dict) -> dict:
    """Extract rate breakdown from an export entry's rates array."""
    rates_breakdown = {}
    try:
        rates_list = export_entry.get("rates")
        if not isinstance(rates_list, list):
            return {}

        for rate_entry in rates_list:
            if not isinstance(rate_entry, dict):
                continue
            rate_type = rate_entry.get("type")
            if not rate_type:
                continue

            charge_obj = rate_entry.get("charge", {})
            charge_value = charge_obj.get("value", 0) if isinstance(charge_obj, dict) else 0

            pct = float(rate_entry.get("percentOfTotal", 0))
            pct_display = round(pct, 2) if pct > 1.0 else round(pct * 100, 2)

            rates_breakdown[rate_type] = {
                "consumption": float(rate_entry.get("consumption", 0)),
                "charge": abs(float(charge_value)),
                "percent": pct_display,
                "available": True,
            }
    except Exception as err:
        _LOGGER.error("Error processing rate breakdown for %s: %s", period, err)

    return rates_breakdown


def _build_daily_map(daily_data: dict) -> dict:
    """Build a date-keyed map of daily solar + export data."""
    daily_map = {}
    solar_entries = daily_data.get("solar") or []
    export_entries = daily_data.get("export") or []

    for entry in solar_entries:
        period_from = entry.get("periodFrom", "")
        if not period_from:
            continue
        try:
            entry_date = datetime.fromisoformat(period_from.replace("Z", "+00:00"))
            date_key = entry_date.strftime("%Y-%m-%d")
            if date_key not in daily_map:
                daily_map[date_key] = _new_daily_entry(entry_date, date_key)
            daily_map[date_key]["solar_consumption"] = entry.get("consumption", 0)
            daily_map[date_key]["solar_charge"] = entry.get("charge", {}).get("value", 0)
        except (ValueError, TypeError):
            continue

    for entry in export_entries:
        period_from = entry.get("periodFrom", "")
        if not period_from:
            continue
        try:
            entry_date = datetime.fromisoformat(period_from.replace("Z", "+00:00"))
            date_key = entry_date.strftime("%Y-%m-%d")
            if date_key not in daily_map:
                daily_map[date_key] = _new_daily_entry(entry_date, date_key)

            daily_map[date_key].setdefault("grid_rates_kwh", {})
            daily_map[date_key].setdefault("grid_rates_aud", {})
            daily_map[date_key].setdefault("periodFrom", entry.get("periodFrom"))
            daily_map[date_key].setdefault("periodTo", entry.get("periodTo"))

            charge_type = entry.get("charge", {}).get("type", "DEBIT")
            consumption = entry.get("consumption", 0)
            charge_value = entry.get("charge", {}).get("value", 0)

            if charge_type == "CREDIT":
                daily_map[date_key]["return_to_grid"] += consumption
                daily_map[date_key]["return_to_grid_charge"] += charge_value
            else:
                daily_map[date_key]["grid_consumption"] += consumption
                daily_map[date_key]["grid_charge"] += charge_value

            # Extract per-rate breakdown
            rates_list = entry.get("rates") or []
            if isinstance(rates_list, list):
                for rate_entry in rates_list:
                    if not isinstance(rate_entry, dict):
                        continue
                    rate_type = rate_entry.get("type")
                    if not rate_type:
                        continue
                    rate_consumption = rate_entry.get("consumption", 0)
                    charge_obj = rate_entry.get("charge", {})
                    rate_charge = abs(charge_obj.get("value", 0)) if isinstance(charge_obj, dict) else 0

                    daily_map[date_key]["grid_rates_kwh"][rate_type] = (
                        daily_map[date_key]["grid_rates_kwh"].get(rate_type, 0) + rate_consumption
                    )
                    daily_map[date_key]["grid_rates_aud"][rate_type] = (
                        daily_map[date_key]["grid_rates_aud"].get(rate_type, 0) + rate_charge
                    )
        except (ValueError, TypeError):
            continue

    return daily_map


def _new_daily_entry(entry_date: datetime, date_key: str) -> dict:
    """Create a fresh daily entry dict."""
    return {
        "date": date_key,
        "day_name": entry_date.strftime("%A"),
        "day": entry_date.day,
        "month": entry_date.month,
        "year": entry_date.year,
        "solar_consumption": 0,
        "solar_charge": 0,
        "grid_consumption": 0,
        "grid_charge": 0,
        "return_to_grid": 0,
        "return_to_grid_charge": 0,
        "grid_rates_kwh": {},
        "grid_rates_aud": {},
    }


def _sum_daily(entries: list[dict], key: str) -> float:
    """Sum a field across daily entries."""
    return sum(d.get(key, 0) for d in entries)


def _aggregate_period(entries: list[dict]) -> dict:
    """Aggregate daily entries into a period summary."""
    return {
        "solar_consumption": _sum_daily(entries, "solar_consumption"),
        "solar_charge": _sum_daily(entries, "solar_charge"),
        "grid_consumption": _sum_daily(entries, "grid_consumption"),
        "grid_charge": _sum_daily(entries, "grid_charge"),
        "return_to_grid": _sum_daily(entries, "return_to_grid"),
        "return_to_grid_charge": _sum_daily(entries, "return_to_grid_charge"),
        "days": len(entries),
    }


def _add_aggregations(processed: dict, all_daily: list[dict], now) -> None:
    """Add last_3_days, last_7_days, month_to_date, last_month aggregations."""
    current_month = now.month
    current_year = now.year

    # Last 3 days (oldest to newest)
    processed["last_3_days"] = list(reversed(all_daily[:3])) if all_daily else []

    # Last 7 days
    last_7 = all_daily[:7] if len(all_daily) >= 7 else all_daily
    if last_7:
        processed["last_7_days"] = _aggregate_period(last_7)

    # Month to date
    mtd = [d for d in all_daily if d["month"] == current_month and d["year"] == current_year]
    if mtd:
        processed["month_to_date"] = _aggregate_period(mtd)

    # Last month
    last_month_num = current_month - 1 if current_month > 1 else 12
    last_month_year = current_year if current_month > 1 else current_year - 1
    last_month = [d for d in all_daily if d["month"] == last_month_num and d["year"] == last_month_year]
    if last_month:
        processed["last_month"] = _aggregate_period(last_month)


def _add_monthly_breakdowns(processed: dict, daily_data: dict, now) -> None:
    """Add current month daily breakdown lists for graphing."""
    current_month = now.month
    current_year = now.year
    solar_entries = daily_data.get("solar") or []
    export_entries = daily_data.get("export") or []

    solar_breakdown = []
    grid_breakdown = []
    return_breakdown = []

    for entry in solar_entries:
        period_from = entry.get("periodFrom", "")
        if not period_from:
            continue
        try:
            entry_date = datetime.fromisoformat(period_from.replace("Z", "+00:00"))
            if entry_date.month == current_month and entry_date.year == current_year:
                solar_breakdown.append({
                    "date": entry_date.strftime("%Y-%m-%d"),
                    "day": entry_date.day,
                    "consumption": entry.get("consumption", 0),
                    "charge": entry.get("charge", {}).get("value", 0),
                    "read_type": entry.get("readType", ""),
                })
        except (ValueError, TypeError):
            continue

    for entry in export_entries:
        period_from = entry.get("periodFrom", "")
        if not period_from:
            continue
        try:
            entry_date = datetime.fromisoformat(period_from.replace("Z", "+00:00"))
            if entry_date.month == current_month and entry_date.year == current_year:
                charge_type = entry.get("charge", {}).get("type", "DEBIT")
                daily_entry = {
                    "date": entry_date.strftime("%Y-%m-%d"),
                    "day": entry_date.day,
                    "consumption": entry.get("consumption", 0),
                    "charge": entry.get("charge", {}).get("value", 0),
                    "read_type": entry.get("readType", ""),
                    "charge_type": charge_type,
                }
                if charge_type == "CREDIT":
                    return_breakdown.append(daily_entry)
                else:
                    grid_breakdown.append(daily_entry)
        except (ValueError, TypeError):
            continue

    processed["monthly"]["solar_daily_breakdown"] = sorted(solar_breakdown, key=lambda x: x["date"])
    processed["monthly"]["grid_daily_breakdown"] = sorted(grid_breakdown, key=lambda x: x["date"])
    processed["monthly"]["return_daily_breakdown"] = sorted(return_breakdown, key=lambda x: x["date"])

    if solar_breakdown:
        processed["monthly"]["solar_daily_avg"] = round(
            sum(d["consumption"] for d in solar_breakdown) / len(solar_breakdown), 2
        )
        processed["monthly"]["solar_daily_max"] = round(
            max(d["consumption"] for d in solar_breakdown), 2
        )
        processed["monthly"]["solar_charge_daily_avg"] = round(
            sum(d["charge"] for d in solar_breakdown) / len(solar_breakdown), 2
        )


def _compute_all_time(monthly_data: dict) -> dict:
    """Compute all-time aggregation from monthly data."""
    all_time_rates = {}
    all_time_solar_consumption = 0.0
    all_time_solar_charge = 0.0
    months_included = 0
    earliest_date = None
    latest_date = None

    for entry in (monthly_data.get("export") or []):
        months_included += 1
        period_from = entry.get("periodFrom")
        period_to = entry.get("periodTo")
        if period_from and (not earliest_date or period_from < earliest_date):
            earliest_date = period_from
        if period_to and (not latest_date or period_to > latest_date):
            latest_date = period_to

        for rate_entry in (entry.get("rates") or []):
            if not isinstance(rate_entry, dict):
                continue
            rate_type = rate_entry.get("type")
            if not rate_type:
                continue
            charge_obj = rate_entry.get("charge", {})
            charge_value = charge_obj.get("value", 0) if isinstance(charge_obj, dict) else 0

            if rate_type not in all_time_rates:
                all_time_rates[rate_type] = {"consumption": 0, "charge": 0, "available": True}
            all_time_rates[rate_type]["consumption"] += float(rate_entry.get("consumption", 0))
            all_time_rates[rate_type]["charge"] += abs(float(charge_value))

    for solar_entry in (monthly_data.get("solar") or []):
        if isinstance(solar_entry, dict):
            all_time_solar_consumption += solar_entry.get("consumption", 0)
            charge_obj = solar_entry.get("charge", {})
            if isinstance(charge_obj, dict):
                all_time_solar_charge += abs(charge_obj.get("value", 0))

    return {
        "rate_breakdown": all_time_rates,
        "solar_consumption": round(all_time_solar_consumption, 3),
        "solar_charge": round(all_time_solar_charge, 2),
        "periodFrom": earliest_date,
        "periodTo": latest_date,
        "months_included": months_included,
    }
