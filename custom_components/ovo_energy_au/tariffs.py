"""Plan detection and scheduled tariff helpers.

OVO returns the prices for a product but not a complete distributor-specific
schedule. Fixed product windows (Free 3, Free 4 and EV overnight) can therefore
be applied automatically; peak/off-peak periods use the user's configured
window. A non-zero super-off-peak price on The One Plan is the currently
published United Energy structure reported in issue #79.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .const import (
    AU_TIMEZONE,
    PLAN_BASIC,
    PLAN_EV,
    PLAN_FREE_3,
    PLAN_FREE_4,
    PLAN_ONE,
)
from .models import PlanConfig


def detect_plan_type(plan_name: str) -> str | None:
    """Return the internal plan type for a recognised OVO product name."""
    normalized = " ".join((plan_name or "").upper().replace("-", " ").split())
    compact = normalized.replace(" ", "")
    if "FREE4" in compact:
        return PLAN_FREE_4
    if "FREE3" in compact:
        return PLAN_FREE_3
    if "EV" in normalized.split() or "EVPLAN" in compact:
        return PLAN_EV
    if "ONE" in normalized.split() or "ONEPLAN" in compact:
        return PLAN_ONE
    if "BASIC" in normalized.split() or "BASICPLAN" in compact:
        return PLAN_BASIC
    return None


def get_current_agreement(data: dict | None) -> dict[str, Any]:
    """Extract the active agreement without exposing its identifiers."""
    agreements_data = (data or {}).get("product_agreements", data or {})
    if not isinstance(agreements_data, dict):
        return {}
    agreements = agreements_data.get("productAgreements") or []
    if not isinstance(agreements, list) or not agreements:
        return {}

    valid = [agreement for agreement in agreements if isinstance(agreement, dict)]
    if not valid:
        return {}

    today = datetime.now(AU_TIMEZONE).date()
    active = [
        agreement
        for agreement in valid
        if (_agreement_date(agreement.get("fromDt")) or date.min) <= today
        and (_agreement_date(agreement.get("toDt")) or date.max) >= today
    ]
    # APIs often leave the current agreement open-ended. Prefer the most
    # recently started active agreement so a completed plan remains harmless
    # even when OVO returns it first after a product switch.
    if active:
        return max(
            active,
            key=lambda agreement: _agreement_date(agreement.get("fromDt")) or date.min,
        )

    past = [agreement for agreement in valid if (_agreement_date(agreement.get("fromDt")) or date.min) <= today]
    if past:
        return max(
            past,
            key=lambda agreement: _agreement_date(agreement.get("fromDt")) or date.min,
        )

    # All agreements are future-dated. Select the first upcoming one rather
    # than a later renewal.
    return min(
        valid,
        key=lambda agreement: _agreement_date(agreement.get("fromDt")) or date.max,
    )


def get_current_product(data: dict | None) -> dict[str, Any]:
    """Extract the current product without exposing agreement identifiers."""
    agreement = get_current_agreement(data)
    product = agreement.get("product") or {}
    return product if isinstance(product, dict) else {}


def get_product_rates(data: dict | None) -> dict[str, Any]:
    """Extract the API unit-rate table for tariff calculations."""
    rates = get_current_product(data).get("unitRatesCentsPerKWH") or {}
    return rates if isinstance(rates, dict) else {}


def update_plan_config_rates(plan_config: PlanConfig, data: dict | None) -> None:
    """Refresh fallback rates from the active product agreement in place."""
    rates = get_product_rates(data)
    for rate_key, attribute in (
        ("peak", "peak_rate"),
        ("shoulder", "shoulder_rate"),
        ("offPeak", "off_peak_rate"),
        ("evOffPeak", "ev_rate"),
        ("standard", "flat_rate"),
    ):
        value = _number(rates.get(rate_key))
        if value is not None:
            setattr(plan_config, attribute, value / 100)


def get_tariff_details(
    plan_config: PlanConfig,
    data: dict | None,
    hour: int,
) -> dict[str, Any]:
    """Return the scheduled period, price and next whole-hour transition."""
    hour %= 24
    rates = get_product_rates(data)
    current_period = _period_at_hour(plan_config, rates, hour)
    rate_cents = _rate_for_period(plan_config, rates, current_period)

    next_change = None
    next_period = None
    for offset in range(1, 25):
        candidate_hour = (hour + offset) % 24
        candidate_period = _period_at_hour(plan_config, rates, candidate_hour)
        if candidate_period != current_period:
            next_change = f"{candidate_hour:02d}:00"
            next_period = candidate_period
            break

    details: dict[str, Any] = {
        "current_period": current_period,
        "rate_cents_kwh": round(rate_cents, 4),
        "rate_aud_kwh": round(rate_cents / 100, 4),
        "next_period_change": next_change,
        "next_period": next_period,
        "current_hour": hour,
        "schedule_source": (
            "configured_peak_window_and_plan" if plan_config.has_other_split_window else "plan_and_api_rates"
        ),
    }
    details.update(get_schedule_attributes(plan_config, rates))
    return details


def get_schedule_attributes(
    plan_config: PlanConfig,
    rates: dict[str, Any],
) -> dict[str, Any]:
    """Return privacy-safe schedule metadata for entity attributes."""
    attrs: dict[str, Any] = {}
    if plan_config.has_other_split_window:
        attrs["peak_window"] = _format_window(plan_config.peak_start_hour, plan_config.peak_end_hour)

    plan_type = plan_config.plan_type
    if plan_type == PLAN_FREE_3:
        attrs["free_window"] = "11:00-14:00"
    elif plan_type == PLAN_FREE_4:
        attrs["free_window"] = "11:00-15:00"
    elif plan_type == PLAN_EV:
        attrs["ev_off_peak_window"] = "00:00-06:00"
        super_rate = _number(rates.get("superOffPeak"))
        if super_rate is not None:
            attrs["free_window" if super_rate == 0 else "super_off_peak_window"] = (
                "11:00-14:00" if super_rate == 0 else _format_window(11, _paid_super_end(plan_config))
            )
    elif plan_type == PLAN_ONE:
        super_rate = _number(rates.get("superOffPeak"))
        if super_rate is not None and super_rate > 0:
            attrs["super_off_peak_window"] = _format_window(11, _paid_super_end(plan_config))

    return attrs


def _period_at_hour(
    plan_config: PlanConfig,
    rates: dict[str, Any],
    hour: int,
) -> str:
    """Resolve a whole-hour period, applying special windows first."""
    plan_type = plan_config.plan_type

    if plan_type == PLAN_EV and _in_window(hour, 0, 6):
        return "EV Off-Peak"
    if plan_type == PLAN_FREE_3 and _in_window(hour, 11, 14):
        return "Super Off-Peak (FREE)"
    if plan_type == PLAN_FREE_4 and _in_window(hour, 11, 15):
        return "Super Off-Peak (FREE)"

    super_rate = _number(rates.get("superOffPeak"))
    if plan_type == PLAN_EV and super_rate is not None:
        if super_rate == 0 and _in_window(hour, 11, 14):
            return "Super Off-Peak (FREE)"
        if super_rate > 0 and _in_window(hour, 11, _paid_super_end(plan_config)):
            return "Super Off-Peak"
    if (
        plan_type == PLAN_ONE
        and super_rate is not None
        and super_rate > 0
        and _in_window(hour, 11, _paid_super_end(plan_config))
    ):
        return "Super Off-Peak"

    if plan_config.has_other_split_window:
        if _in_window(hour, plan_config.peak_start_hour, plan_config.peak_end_hour):
            return "Peak"
        return "Off-Peak"
    return "Standard"


def _rate_for_period(
    plan_config: PlanConfig,
    rates: dict[str, Any],
    period: str,
) -> float:
    """Resolve a cents/kWh value, preferring the live product agreement."""
    if period == "Super Off-Peak (FREE)":
        # The product contract defines this period as $0. OVO has previously
        # returned generic/non-applicable fields in the rate table, so never
        # allow a placeholder to make a FREE state display a non-zero price.
        return 0.0

    fallbacks = {
        "Peak": ("peak", plan_config.peak_rate * 100),
        "Off-Peak": ("offPeak", plan_config.off_peak_rate * 100),
        "EV Off-Peak": ("evOffPeak", plan_config.ev_rate * 100),
        "Super Off-Peak": ("superOffPeak", plan_config.shoulder_rate * 100),
    }
    if period in fallbacks:
        key, fallback = fallbacks[period]
        value = _number(rates.get(key), fallback)
        return fallback if value is None else value

    for key in ("standard", "peak", "shoulder", "offPeak"):
        value = _number(rates.get(key))
        if value is not None:
            return value
    fallback = plan_config.flat_rate if plan_config.plan_type == PLAN_ONE else plan_config.peak_rate
    return fallback * 100


def _in_window(hour: int, start: int | None, end: int | None) -> bool:
    """Return whether hour is inside a half-open, possibly overnight window."""
    if start is None or end is None or start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def _format_window(start: int | None, end: int | None) -> str:
    """Format a validated plan window."""
    if start is None or end is None:
        return ""
    return f"{int(start):02d}:00-{int(end):02d}:00"


def _paid_super_end(plan_config: PlanConfig) -> int:
    """Use the configured afternoon peak boundary when it is applicable."""
    start = plan_config.peak_start_hour
    if plan_config.has_other_split_window and start is not None and 11 < start <= 23:
        return start
    return 16


def _number(value: Any, fallback: float | None = None) -> float | None:
    """Coerce an API number while rejecting booleans and malformed values."""
    if isinstance(value, bool):
        return fallback
    try:
        return float(value) if value is not None else fallback
    except (TypeError, ValueError):
        return fallback


def _agreement_date(value: Any) -> date | None:
    """Parse an agreement date or ISO timestamp."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
