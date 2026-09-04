"""Interval data processing (daily/monthly/yearly)."""

from __future__ import annotations

import logging
from datetime import date, datetime

from homeassistant.util import dt as dt_util

from ..const import AU_TIMEZONE
from ..time_utils import parse_ovo_datetime
from .billing import current_cycle_bounds, previous_cycle_bounds

_LOGGER = logging.getLogger(__name__)


def _entry_date(entry: dict) -> date | None:
    """Return a daily entry's calendar date from its year/month/day fields."""
    try:
        return date(entry["year"], entry["month"], entry["day"])
    except (KeyError, TypeError, ValueError):
        return None


def _parse_entry_date(period_from: str) -> datetime:
    """Parse an API period without depending on the HA host timezone."""
    result = parse_ovo_datetime(period_from)
    if result is None:
        raise ValueError("Invalid OVO period timestamp")
    return result


def _safe_charge(entry: dict) -> dict:
    """Safely extract charge dict from an API entry.

    The OVO API returns charge: null (not missing) for hourly data entries.
    entry.get("charge", {}) returns None when key exists with null value.
    This helper ensures we always get a dict.
    """
    charge = entry.get("charge")
    return charge if isinstance(charge, dict) else {}


def process_interval_data(data: dict, billing_cycle_day: int = 1) -> dict:
    """Process interval data from the OVO API.

    ``billing_cycle_day`` (1-31) sets which day the billing cycle starts, so
    month-to-date and last-cycle aggregations follow the user's real bill
    period. The default of 1 gives calendar-month boundaries.

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

    # Extract OVO savings data (EV/Free plan vs One Plan comparison)
    for period in ["daily", "monthly", "yearly"]:
        period_data = data.get(period)
        if not period_data or not isinstance(period_data, dict):
            continue
        savings_list = period_data.get("savings") or []
        if savings_list and isinstance(savings_list, list):
            dated_savings = _latest_period_entries(savings_list)
            latest_savings = dated_savings[0] if dated_savings else savings_list[-1]
            amount = latest_savings.get("amount") or {}
            # Don't abs() — negative savings means user would save more on another plan
            processed[period]["ovo_savings"] = amount.get("value", 0)
            processed[period]["ovo_savings_description"] = latest_savings.get("description", "")

    # Build daily map for aggregations
    daily_data = data.get("daily")
    if daily_data and isinstance(daily_data, dict):
        daily_map = _build_daily_map(daily_data)
        all_daily_entries = sorted(daily_map.values(), key=lambda x: x["date"], reverse=True)[:90]
        processed["all_daily_entries"] = all_daily_entries

        # Sydney time, so "current month" matches the AU billing day even
        # when HA itself is configured for a different timezone
        now = dt_util.now(AU_TIMEZONE)
        _add_aggregations(processed, all_daily_entries, now, billing_cycle_day)
        _add_monthly_breakdowns(processed, daily_data, now, billing_cycle_day)

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
    """Select the newest timestamp, then combine all readings for that period."""
    result = {}
    solar = _latest_period_entries(period_data.get("solar"))
    if solar:
        result["solar_consumption"] = sum(e.get("consumption", 0) or 0 for e in solar)
        result["solar_charge"] = sum(_safe_charge(e).get("value", 0) or 0 for e in solar)
        result["solar_latest"] = solar[0]

    entries = _latest_period_entries(period_data.get("export"))
    if entries:
        result.update(grid_consumption=0, grid_charge=0, return_to_grid=0, return_to_grid_charge=0)
        result["grid_latest"] = entries[0]
        merged_rates = {}
        for entry in entries:
            charge = _safe_charge(entry)
            consumption = entry.get("consumption", 0) or 0
            value = charge.get("value", 0) or 0
            if charge.get("type") == "CREDIT":
                result["return_to_grid"] += consumption
                result["return_to_grid_charge"] += value
                continue  # Export credits are not grid purchase tariff buckets.
            result["grid_consumption"] += consumption
            result["grid_charge"] += value
            for rate_type, rate in _extract_rate_breakdown(period, entry).items():
                bucket = merged_rates.setdefault(rate_type, {"consumption": 0, "charge": 0, "percent": 0, "available": True})
                bucket["consumption"] += rate.get("consumption", 0)
                bucket["charge"] += rate.get("charge", 0)
        total = sum(rate["consumption"] for rate in merged_rates.values())
        for rate in merged_rates.values():
            rate["percent"] = round(rate["consumption"] / total * 100, 2) if total else 0
        result["rate_breakdown"] = merged_rates
    return result


def _latest_period_entries(entries: object) -> list[dict]:
    """Ignore undated records rather than calling arbitrary array order latest."""
    if not isinstance(entries, list):
        return []
    dated = [(timestamp, entry) for entry in entries
             if isinstance(entry, dict) and (timestamp := parse_ovo_datetime(entry.get("periodFrom"))) is not None]
    if not dated:
        return []
    latest = max(timestamp for timestamp, _ in dated)
    return [entry for timestamp, entry in dated if timestamp == latest]


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

            charge_obj = _safe_charge(rate_entry)
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
        _LOGGER.error("Error processing rate breakdown for %s: %s", period, type(err).__name__)

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
            entry_date = _parse_entry_date(period_from)
            date_key = entry_date.strftime("%Y-%m-%d")
            if date_key not in daily_map:
                daily_map[date_key] = _new_daily_entry(entry_date, date_key)
            daily_map[date_key]["solar_consumption"] += entry.get("consumption", 0) or 0
            daily_map[date_key]["solar_charge"] += _safe_charge(entry).get("value", 0) or 0
        except (ValueError, TypeError):
            continue

    for entry in export_entries:
        period_from = entry.get("periodFrom", "")
        if not period_from:
            continue
        try:
            entry_date = _parse_entry_date(period_from)
            date_key = entry_date.strftime("%Y-%m-%d")
            if date_key not in daily_map:
                daily_map[date_key] = _new_daily_entry(entry_date, date_key)

            daily_map[date_key].setdefault("grid_rates_kwh", {})
            daily_map[date_key].setdefault("grid_rates_aud", {})
            daily_map[date_key].setdefault("periodFrom", entry.get("periodFrom"))
            daily_map[date_key].setdefault("periodTo", entry.get("periodTo"))

            charge_type = _safe_charge(entry).get("type", "DEBIT")
            consumption = entry.get("consumption", 0)
            charge_value = _safe_charge(entry).get("value", 0)

            if charge_type == "CREDIT":
                daily_map[date_key]["return_to_grid"] += consumption
                daily_map[date_key]["return_to_grid_charge"] += charge_value
            else:
                daily_map[date_key]["grid_consumption"] += consumption
                daily_map[date_key]["grid_charge"] += charge_value

            # Grid rate buckets must never include solar export credits.
            if charge_type == "CREDIT":
                continue
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
                    charge_obj = _safe_charge(rate_entry)
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


def _add_aggregations(processed: dict, all_daily: list[dict], now, billing_cycle_day: int = 1) -> None:
    """Add last_3_days, last_7_days, month_to_date, last_month aggregations.

    ``month_to_date`` and ``last_month`` follow the configured billing cycle
    (``billing_cycle_day``); with the default of 1 they are calendar months.
    """
    today = now.date()

    # Last 3 days (oldest to newest)
    processed["last_3_days"] = list(reversed(all_daily[:3])) if all_daily else []

    # Last 7 days
    last_7 = all_daily[:7] if len(all_daily) >= 7 else all_daily
    if last_7:
        processed["last_7_days"] = _aggregate_period(last_7)

    # Month to date — current billing cycle so far
    cycle_start, cycle_next = current_cycle_bounds(today, billing_cycle_day)
    mtd = [
        d for d in all_daily
        if (ed := _entry_date(d)) is not None and cycle_start <= ed < cycle_next
    ]
    if mtd:
        processed["month_to_date"] = _aggregate_period(mtd)

    # Last month — the previous complete billing cycle
    prev_start, prev_next = previous_cycle_bounds(today, billing_cycle_day)
    last_month = [
        d for d in all_daily
        if (ed := _entry_date(d)) is not None and prev_start <= ed < prev_next
    ]
    if last_month:
        processed["last_month"] = _aggregate_period(last_month)


def _add_monthly_breakdowns(processed: dict, daily_data: dict, now, billing_cycle_day: int = 1) -> None:
    """Add current billing-cycle daily breakdown lists for graphing."""
    cycle_start, cycle_next = current_cycle_bounds(now.date(), billing_cycle_day)
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
            entry_date = _parse_entry_date(period_from)
            if cycle_start <= entry_date.date() < cycle_next:
                solar_breakdown.append({
                    "date": entry_date.strftime("%Y-%m-%d"),
                    "day": entry_date.day,
                    "consumption": entry.get("consumption", 0),
                    "charge": _safe_charge(entry).get("value", 0),
                    "read_type": entry.get("readType", ""),
                })
        except (ValueError, TypeError):
            continue

    for entry in export_entries:
        period_from = entry.get("periodFrom", "")
        if not period_from:
            continue
        try:
            entry_date = _parse_entry_date(period_from)
            if cycle_start <= entry_date.date() < cycle_next:
                charge_type = _safe_charge(entry).get("type", "DEBIT")
                daily_entry = {
                    "date": entry_date.strftime("%Y-%m-%d"),
                    "day": entry_date.day,
                    "consumption": entry.get("consumption", 0),
                    "charge": _safe_charge(entry).get("value", 0),
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
    seen_months = set()
    earliest_date = None
    latest_date = None

    for entry in (monthly_data.get("export") or []):
        if not isinstance(entry, dict) or _safe_charge(entry).get("type") == "CREDIT":
            continue
        period_from = entry.get("periodFrom")
        if period_from:
            seen_months.add(period_from[:7])  # Track unique YYYY-MM
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
            charge_obj = _safe_charge(rate_entry)
            charge_value = charge_obj.get("value", 0) if isinstance(charge_obj, dict) else 0

            if rate_type not in all_time_rates:
                all_time_rates[rate_type] = {"consumption": 0, "charge": 0, "available": True}
            all_time_rates[rate_type]["consumption"] += float(rate_entry.get("consumption", 0))
            all_time_rates[rate_type]["charge"] += abs(float(charge_value))

    for solar_entry in (monthly_data.get("solar") or []):
        if isinstance(solar_entry, dict):
            all_time_solar_consumption += solar_entry.get("consumption", 0)
            charge_obj = _safe_charge(solar_entry)
            if isinstance(charge_obj, dict):
                all_time_solar_charge += abs(charge_obj.get("value", 0))

    return {
        "rate_breakdown": all_time_rates,
        "solar_consumption": round(all_time_solar_consumption, 3),
        "solar_charge": round(all_time_solar_charge, 2),
        "periodFrom": earliest_date,
        "periodTo": latest_date,
        "months_included": len(seen_months),
    }
