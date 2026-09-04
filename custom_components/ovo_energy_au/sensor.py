"""Sensor platform for OVO Energy Australia.

This file is the HA entry point. It assembles sensors from definitions
and specialized classes, keeping the registration logic separate from
the sensor business logic.
"""

from __future__ import annotations

import datetime as dt
import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PLAN_EV, PLAN_FREE_3, PLAN_FREE_4, PLAN_ONE
from .sensors.base import (
    AU_TIMEZONE,
    OVOBaseSensor,
    OVOEnergySensor,
)
from .sensors.definitions import (
    ANALYTICS_SENSORS,
    ENERGY_SENSORS,
    calculate_free_savings,
    get_rate_value,
)
from .sensors.vehicle import create_vehicle_sensors
from .tariffs import (
    detect_plan_type,
    get_current_agreement,
    get_current_product,
    get_product_rates,
    get_schedule_attributes,
    get_tariff_details,
)
from .time_utils import parse_ovo_datetime

_LOGGER = logging.getLogger(__name__)

_RETIRED_SENSOR_KEYS = {
    "daily_ovo_savings",
    "monthly_ovo_savings",
    "yearly_ovo_savings",
    "latest_bill_amount",
    "latest_bill_closing_balance",
    "latest_bill_opening_balance",
    "tariff_peak_rate",
    "tariff_shoulder_rate",
    "tariff_off_peak_rate",
    "tariff_ev_off_peak_rate",
    "tariff_feed_in_rate",
    "tariff_standing_charge",
    "monthly_projection_total",
    "monthly_projection_remaining",
    "monthly_daily_average",
}
_RETIRED_ROTATING_SENSOR_KEYS = {
    *(
        f"day_{day}_{metric}"
        for day in range(1, 8)
        for metric in (
            "solar_consumption",
            "solar_charge",
            "grid_consumption",
            "grid_charge",
        )
    ),
    *(
        f"day_{day}_grid_rate_{rate}_{metric}"
        for day in range(1, 8)
        for rate in ("peak", "shoulder", "offpeak", "ev_offpeak", "other", "free_3")
        for metric in ("consumption", "charge")
    ),
    *(
        f"history_day_{day}_{rate}"
        for day in range(7)
        for rate in ("total", "ev_offpeak", "free_3", "other")
    ),
    *(
        f"hourly_{kind}_{day}d_ago"
        for kind in ("solar", "grid", "export")
        for day in range(1, 8)
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OVO Energy Australia sensor platform."""
    coordinator = entry.runtime_data
    _remove_retired_registry_entities(hass, entry, coordinator.account_id)
    sensors: list[SensorEntity] = []

    # ── Data-driven sensors from definitions ──
    for defn in ENERGY_SENSORS + ANALYTICS_SENSORS:
        key, name, unit, device_class, state_class, icon, value_fn, category = defn
        sensors.append(OVOEnergySensor(
            coordinator, key, name, unit, device_class, state_class, icon, value_fn, category
        ))

    # ── Rate breakdown sensors (per period) ──
    for period, label in [("daily", "Yesterday"), ("monthly", "This Month"), ("yearly", "This Year")]:
        _add_rate_sensors(sensors, coordinator, period, label)

    # ── Rate breakdown with counterfactuals ──
    for period, label in [("daily", "Yesterday"), ("monthly", "This Month"),
                          ("yearly", "This Year"), ("all_time", "All Time")]:
        sensors.append(OVORateBreakdownSensor(coordinator, period, label))

    # ── Per-hour yesterday sensors ── (removed: data available in hourly day sensor attributes)

    # ── Plan diagnostic sensor ──
    sensors.append(OVOPlanSensor(coordinator))

    # ── Integration health diagnostic sensor ──
    sensors.append(OVOHealthSensor(coordinator))

    # ── Tariff period indicator ──
    sensors.append(OVOTariffPeriodSensor(coordinator))

    # ── Plan comparison / recommendation ──
    sensors.append(OVORateComparisonSensor(coordinator))

    # ── Real bills + last-3-days + payments + referral (rich attributes) ──
    sensors.append(OVOLatestBillSensor(coordinator))
    sensors.append(OVOLast3DaysSensor(coordinator))
    sensors.append(OVOLatestPaymentSensor(coordinator))
    sensors.append(OVOReferralSensor(coordinator))
    sensors.append(OVOFlexSensor(coordinator))

    # ── HA Energy Dashboard (cumulative month-to-date, total + last_reset) ──
    sensors.append(OVOEnergyDashboardSensor(
        coordinator, "energy_grid_import", "Grid Import (Energy Dashboard)",
        "grid_consumption", "mdi:transmission-tower-import"))
    sensors.append(OVOEnergyDashboardSensor(
        coordinator, "energy_grid_export", "Grid Export (Energy Dashboard)",
        "return_to_grid", "mdi:transmission-tower-export"))
    sensors.append(OVOEnergyDashboardSensor(
        coordinator, "energy_solar_production", "Solar Production (Energy Dashboard)",
        "solar_consumption", "mdi:solar-power"))

    # ── Connected vehicles ──
    # Vehicle entities live on a separate physical device and are discovered
    # from the first refresh.  The listener also handles a vehicle that appears
    # after setup (for example, following a temporary Kaluza outage).
    known_vehicle_ids: set[str] = set()
    for vehicle in (coordinator.data or {}).get("vehicles") or []:
        if vehicle.get("id"):
            known_vehicle_ids.add(vehicle["id"])
            sensors.extend(create_vehicle_sensors(coordinator, vehicle))

    async_add_entities(sensors)

    @callback
    def _async_add_new_vehicles() -> None:
        new_entities: list[SensorEntity] = []
        for vehicle in (coordinator.data or {}).get("vehicles") or []:
            vehicle_id = vehicle.get("id")
            if not vehicle_id or vehicle_id in known_vehicle_ids:
                continue
            known_vehicle_ids.add(vehicle_id)
            new_entities.extend(create_vehicle_sensors(coordinator, vehicle))
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_vehicles))


# ─── Sensor factory helpers ──────────────────────────────────────────


def _remove_retired_registry_entities(hass, entry, account_id: str) -> None:
    """Remove only known obsolete entities belonging to this config entry."""
    registry = er.async_get(hass)
    unique_id_prefix = f"{account_id}_"
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        unique_id = registry_entry.unique_id or ""
        if not unique_id.startswith(unique_id_prefix):
            continue
        sensor_key = unique_id[len(unique_id_prefix):]
        if (
            sensor_key in _RETIRED_SENSOR_KEYS
            or sensor_key in _RETIRED_ROTATING_SENSOR_KEYS
        ):
            registry.async_remove(registry_entry.entity_id)


def _add_rate_sensors(sensors: list, coordinator, period: str, label: str) -> None:
    """Add EV/Free/Other rate breakdown sensors for a period."""
    rate_configs = [
        ("ev_offpeak", "EV Off-Peak", "EV_OFFPEAK", "mdi:ev-station"),
        ("free_3", "Free Period", "FREE_3", "mdi:gift"),
        ("other", "Other Rates", "OTHER", "mdi:chart-bar"),
    ]
    for suffix, name, rate_type, icon in rate_configs:
        sensors.append(OVOEnergySensor(
            coordinator,
            f"{period}_{suffix}_consumption",
            f"{name} Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            icon,
            lambda d, p=period, rt=rate_type: get_rate_value(d, p, rt, "consumption"),
            f"Rate Breakdown - {label}",
        ))
        if rate_type == "FREE_3":
            sensors.append(OVOEnergySensor(
                coordinator,
                f"{period}_{suffix}_savings",
                f"{name} Savings",
                "AUD",
                SensorDeviceClass.MONETARY,
                SensorStateClass.TOTAL,
                "mdi:piggy-bank",
                lambda d, p=period: calculate_free_savings(d, p, coordinator),
                f"Rate Breakdown - {label}",
            ))
        else:
            sensors.append(OVOEnergySensor(
                coordinator,
                f"{period}_{suffix}_cost",
                f"{name} Cost",
                "AUD",
                SensorDeviceClass.MONETARY,
                SensorStateClass.TOTAL,
                "mdi:currency-usd",
                lambda d, p=period, rt=rate_type: get_rate_value(d, p, rt, "charge"),
                f"Rate Breakdown - {label}",
            ))


# ─── Specialized sensor classes ──────────────────────────────────────


class OVORateBreakdownSensor(OVOBaseSensor):
    """Rate breakdown sensor with counterfactual calculations."""

    def __init__(self, coordinator, period: str, period_label: str):
        super().__init__(
            coordinator, f"rate_breakdown_{period}",
            f"Rate Breakdown - {period_label}",
            "Rate Breakdown",
        )
        self._period = period
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:cash-multiple"
        self._cached_breakdown = {}
        self._last_update = None

    def _get_breakdown(self) -> dict:
        """Return cached breakdown, recomputing only on coordinator update."""
        update_time = getattr(self.coordinator, 'last_update_success_time', None)
        if update_time != self._last_update:
            self._cached_breakdown = self._compute_breakdown()
            self._last_update = update_time
        return self._cached_breakdown

    @property
    def native_value(self) -> float | None:
        breakdown = self._get_breakdown()
        return breakdown.get("total_kwh") if breakdown else None

    @property
    def extra_state_attributes(self) -> dict:
        return self._get_breakdown() or {}

    def _compute_breakdown(self) -> dict:
        """Calculate rate breakdown with counterfactual costs."""
        data = self.coordinator.data
        if not data:
            return {}

        period_data = data.get(self._period, {})
        rate_breakdown = period_data.get("rate_breakdown", {})

        solar_kwh = period_data.get("solar_consumption", 0) or 0
        solar_credit = abs(period_data.get("solar_charge", 0) or 0)

        ev_kwh = rate_breakdown.get("EV_OFFPEAK", {}).get("consumption", 0)
        ev_cost = rate_breakdown.get("EV_OFFPEAK", {}).get("charge", 0)

        free_kwh = sum(
            e.get("consumption", 0)
            for rt, e in rate_breakdown.items()
            if "FREE" in rt and e.get("available")
        )
        free_cost = sum(
            e.get("charge", 0)
            for rt, e in rate_breakdown.items()
            if "FREE" in rt and e.get("available")
        )

        other_kwh = rate_breakdown.get("OTHER", {}).get("consumption", 0)
        other_cost = rate_breakdown.get("OTHER", {}).get("charge", 0)
        other_rate = other_cost / other_kwh if other_kwh > 0 else 0

        ev_if_other = ev_kwh * other_rate
        free_if_other = free_kwh * other_rate

        result = {
            "source": "ovo_graphql",
            "ev_offpeak_kwh": round(ev_kwh, 3),
            "ev_offpeak_cost": round(ev_cost, 2),
            "ev_offpeak_cost_if_other": round(ev_if_other, 2),
            "ev_offpeak_savings_vs_other": round(max(0, ev_if_other - ev_cost), 2),
            "free_kwh": round(free_kwh, 3),
            "free_cost": round(free_cost, 2),
            "free_cost_if_other": round(free_if_other, 2),
            "free_savings_vs_other": round(max(0, free_if_other - free_cost), 2),
            "other_kwh": round(other_kwh, 3),
            "other_cost": round(other_cost, 2),
            "other_unit_rate": round(other_rate, 4) if other_rate > 0 else 0,
            "solar_kwh": round(solar_kwh, 3),
            "solar_credit": round(solar_credit, 2),
            "total_kwh": round(ev_kwh + free_kwh + other_kwh, 3),
            "total_cost": round(ev_cost + free_cost + other_cost, 2),
            "total_savings_vs_other": round(
                max(0, ev_if_other - ev_cost) + max(0, free_if_other - free_cost), 2
            ),
        }
        if self._period == "all_time":
            result["months_included"] = period_data.get("months_included", 0)
        return result


class OVOPlanSensor(OVOBaseSensor):
    """Diagnostic sensor displaying plan information."""

    def __init__(self, coordinator):
        super().__init__(coordinator, "plan_information", "Plan Information", "General")
        self._attr_icon = "mdi:file-document-outline"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        pa = self.coordinator.data.get("product_agreements")
        if not pa or not isinstance(pa, dict):
            return "Unknown"
        product = get_current_product(self.coordinator.data)
        if not product:
            return "No Plan"
        return product.get("displayName", "Unknown Plan")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        pa = self.coordinator.data.get("product_agreements")
        if not pa:
            return {"status": "No plan data available"}
        agreement = get_current_agreement(self.coordinator.data)
        if not agreement:
            return {"status": "No product agreements found"}

        product = get_current_product(self.coordinator.data)
        unit_rates = get_product_rates(self.coordinator.data)

        attrs = {
            "plan_name": product.get("displayName", "Unknown"),
            "product_code": product.get("code", "Unknown"),
            "from_date": agreement.get("fromDt", "Unknown"),
            "to_date": agreement.get("toDt", "Unknown"),
        }
        detected_plan = detect_plan_type(product.get("displayName", ""))
        if detected_plan:
            attrs["detected_plan_type"] = detected_plan
        attrs.update(
            get_schedule_attributes(
                self.coordinator.plan_config,
                get_product_rates(self.coordinator.data),
            )
        )

        standing = product.get("standingChargeCentsPerDay", 0)
        if standing:
            attrs["standing_charge_cents_per_day"] = standing
            attrs["standing_charge_aud_per_day"] = round(standing / 100, 2)

        rate_fields = [
            ("peak", "peak"), ("shoulder", "shoulder"), ("offPeak", "off_peak"),
            ("evOffPeak", "ev_off_peak"), ("superOffPeak", "super_off_peak"),
            ("standard", "standard"), ("feedInTariff", "feed_in_tariff"),
            ("CL1", "cl1"),
        ]
        for rate_key, label in rate_fields:
            val = unit_rates.get(rate_key)
            if rate_key == "evOffPeak" and self.coordinator.plan_config.plan_type != PLAN_EV:
                continue
            if (
                rate_key == "superOffPeak"
                and self.coordinator.plan_config.plan_type
                in (PLAN_FREE_3, PLAN_FREE_4)
            ):
                # The Free product contract is authoritative. Do not expose a
                # generic non-zero placeholder as the free-window price.
                val = 0
            if rate_key == "superOffPeak" and not (
                self.coordinator.plan_config.plan_type
                in (PLAN_EV, PLAN_FREE_3, PLAN_FREE_4)
                or (
                    self.coordinator.plan_config.plan_type == PLAN_ONE
                    and isinstance(val, (int, float))
                    and not isinstance(val, bool)
                    and val > 0
                )
            ):
                continue
            if val is not None:
                attrs[f"{label}_cents_kwh"] = val
                attrs[f"{label}_aud_kwh"] = round(val / 100, 4)

        demand = unit_rates.get("demand") or {}
        if isinstance(demand, dict):
            peak_demand = demand.get("peakDemand")
            if peak_demand is not None:
                attrs["demand_peak_cents_kwh"] = peak_demand
                attrs["demand_peak_aud_kwh"] = round(peak_demand / 100, 4)

        if standing:
            attrs["standing_charge_monthly_aud"] = round(standing / 100 * 30.44, 2)
            attrs["standing_charge_yearly_aud"] = round(standing / 100 * 365.25, 2)

        return attrs

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self.coordinator.account_id)},
            "name": "OVO Energy AU",
            "manufacturer": "OVO Energy Australia",
            "model": "Energy Monitor",
        }


class OVOHealthSensor(OVOBaseSensor):
    """Diagnostic sensor showing integration health."""

    def __init__(self, coordinator):
        super().__init__(coordinator, "integration_health", "Integration Health", "General")
        self._attr_icon = "mdi:heart-pulse"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        if not self.coordinator.data:
            return "No Data"
        delay_days = self._usage_data_delay_days()
        if delay_days is not None and delay_days > 2:
            return "Stale Usage Data"
        hourly_status = getattr(self.coordinator, "hourly_data_status", None)
        if hourly_status == "stale":
            return "Hourly Data Stale"
        if hourly_status == "unavailable":
            return "Hourly Data Unavailable"
        return "OK"

    def _usage_data_delay_days(self) -> int | None:
        """Return whole days between today and the newest meter-usage date."""
        all_daily = (self.coordinator.data or {}).get("all_daily_entries", [])
        if not all_daily:
            return None
        newest = all_daily[0].get("date")
        try:
            newest_date = datetime.strptime(newest, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None
        return max(0, (datetime.now(AU_TIMEZONE).date() - newest_date).days)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = {
            "update_interval_minutes": 5,
            "plan_type": self.coordinator.plan_config.plan_type,
            "energy_data_realtime": False,
            "usage_data_expected_delay_days": 1,
            "energy_data_note": "OVO meter usage normally arrives the following day",
        }

        hourly_status = getattr(self.coordinator, "hourly_data_status", None)
        if hourly_status not in {"fresh", "stale", "unavailable"}:
            hourly_status = "unknown"
        attrs["hourly_data_status"] = hourly_status
        attrs["hourly_data_stale"] = hourly_status == "stale"

        hourly_last_success = getattr(
            self.coordinator, "hourly_last_success_time", None
        )
        if isinstance(hourly_last_success, dt.datetime):
            attrs["hourly_last_successful_update"] = hourly_last_success.isoformat()

        hourly_issue = getattr(self.coordinator, "hourly_data_issue", None)
        if isinstance(hourly_issue, str):
            attrs["hourly_data_issue"] = hourly_issue

        if self.coordinator.data:
            all_daily = self.coordinator.data.get("all_daily_entries", [])
            hourly = self.coordinator.data.get("hourly") or {}

            attrs["daily_entries_available"] = len(all_daily)
            attrs["hourly_solar_entries"] = len(hourly.get("solar_entries", []))
            attrs["hourly_grid_entries"] = len(hourly.get("grid_entries", []))
            attrs["has_product_agreements"] = self.coordinator.data.get("product_agreements") is not None
            attrs["has_solar"] = self.coordinator.data.get("has_solar")
            attrs["meter_type"] = self.coordinator.data.get("meter_type")
            attrs["api_timezone"] = self.coordinator.data.get("api_timezone")
            attrs["last_meter_read"] = self.coordinator.data.get("last_meter_read")

            if all_daily:
                attrs["oldest_daily_date"] = all_daily[-1].get("date")
                attrs["newest_daily_date"] = all_daily[0].get("date")
                delay_days = self._usage_data_delay_days()
                attrs["usage_data_delay_days"] = delay_days
                attrs["usage_data_stale"] = delay_days is not None and delay_days > 2

        if self.coordinator.last_update_success_time:
            attrs["last_successful_update"] = self.coordinator.last_update_success_time.isoformat()

        return attrs

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self.coordinator.account_id)},
            "name": "OVO Energy AU",
            "manufacturer": "OVO Energy Australia",
            "model": "Energy Monitor",
        }


class OVOTariffPeriodSensor(OVOBaseSensor):
    """Sensor showing the current tariff/rate period based on time of day."""

    def __init__(self, coordinator):
        super().__init__(coordinator, "current_tariff_period", "Current Tariff Period", "Tariff")
        self._attr_icon = "mdi:clock-time-four"

    @property
    def native_value(self) -> str:
        """Return the plan-appropriate current tariff period."""
        return self._period_details()["current_period"]

    @property
    def extra_state_attributes(self) -> dict:
        return self._period_details()

    @property
    def available(self) -> bool:
        """Do not present expired, future or unavailable auto-detected tariffs."""
        if (getattr(self.coordinator, "auto_detect_plan", False) is True
                and not get_current_product(self.coordinator.data)):
            return False
        return bool(getattr(self.coordinator, "last_update_success", True))

    def _period_details(self) -> dict:
        """Calculate the plan-aware period and rate for the current AU hour."""
        return get_tariff_details(
            self.coordinator.plan_config,
            self.coordinator.data,
            datetime.now(AU_TIMEZONE).hour,
        )

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.account_id)},
            "name": "OVO Energy AU",
            "manufacturer": "OVO Energy Australia",
            "model": "Energy Monitor",
        }


class OVORateComparisonSensor(OVOBaseSensor):
    """One consolidated plan-savings sensor for every API period."""

    def __init__(self, coordinator):
        # Keep the historical unique ID so existing dashboards and automations
        # continue to follow this entity after its user-facing rename.
        super().__init__(coordinator, "plan_comparison", "Plan Savings", "OVO Savings")
        self._attr_icon = "mdi:compare-horizontal"

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        yearly = self.coordinator.data.get("yearly", {})
        savings = yearly.get("ovo_savings", 0)
        if savings and savings > 0:
            return f"Saving ${round(savings, 2)}/year"
        elif savings and savings < 0:
            return "Consider switching plans"
        return "No comparison data"

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data:
            return {}

        attrs = {}

        # Get savings across periods
        daily = self.coordinator.data.get("daily", {})
        monthly = self.coordinator.data.get("monthly", {})
        yearly = self.coordinator.data.get("yearly", {})

        daily_savings = daily.get("ovo_savings", 0) or 0
        monthly_savings = monthly.get("ovo_savings", 0) or 0
        yearly_savings = yearly.get("ovo_savings", 0) or 0

        attrs["daily_savings"] = round(daily_savings, 2)
        attrs["monthly_savings"] = round(monthly_savings, 2)
        attrs["yearly_savings"] = round(yearly_savings, 2)

        # Get the comparison description from savings data
        daily_desc = daily.get("ovo_savings_description", "")
        if daily_desc:
            attrs["comparison_description"] = daily_desc

        # Calculate recommendation
        if yearly_savings > 500:
            attrs["recommendation"] = "Excellent! Your current plan is saving you significantly. Stay on it."
            attrs["rating"] = "Excellent"
        elif yearly_savings > 200:
            attrs["recommendation"] = "Good savings. Your current plan is working well for your usage pattern."
            attrs["rating"] = "Good"
        elif yearly_savings > 50:
            attrs["recommendation"] = "Modest savings. Consider if your usage patterns could be optimized."
            attrs["rating"] = "Fair"
        elif yearly_savings > 0:
            attrs["recommendation"] = "Minimal savings vs the One Plan. Review if EV/Free periods match your usage."
            attrs["rating"] = "Marginal"
        else:
            attrs["recommendation"] = "You may save more on a different plan. Contact OVO to compare options."
            attrs["rating"] = "Consider Switching"

        # Project annual savings from monthly. Skip the first few days of a
        # month — extrapolating 1-2 days of data to a year is wildly unstable.
        if monthly_savings > 0:
            now = datetime.now(AU_TIMEZONE)
            day_of_month = now.day
            if day_of_month >= 3:
                projected_monthly = monthly_savings / day_of_month * 30.44
                projected_annual = projected_monthly * 12
                attrs["projected_annual_savings"] = round(projected_annual, 2)

        # Get plan info
        product = get_current_product(self.coordinator.data)
        if product:
            attrs["current_plan"] = product.get("displayName", "Unknown")
            attrs["compared_to"] = "The One Plan"

        return attrs

class OVOLatestBillSensor(OVOBaseSensor):
    """Most recent issued bill — amount as state, period/balances/PDF in attributes."""

    def __init__(self, coordinator):
        super().__init__(coordinator, "latest_bill", "Latest Bill", "Bills")
        self._attr_icon = "mdi:receipt-text"
        self._attr_native_unit_of_measurement = "AUD"
        self._attr_device_class = SensorDeviceClass.MONETARY

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        total = (self.coordinator.data.get("latest_bill") or {}).get("total")
        return round(float(total), 2) if total is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        bill = self.coordinator.data.get("latest_bill") or {}
        statements = self.coordinator.data.get("statements") or []
        return {
            "period_from": bill.get("period_from"),
            "period_to": bill.get("period_to"),
            "issue_date": bill.get("issue_date"),
            "opening_balance": bill.get("opening_balance"),
            "closing_balance": bill.get("closing_balance"),
            "statement_count": len(statements),
            "recent_bills": [
                {
                    "period_from": s.get("periodFrom"),
                    "period_to": s.get("periodTo"),
                    "issue_date": s.get("issueDate"),
                    "total": ((s.get("charges") or {}).get("total") or {}).get("value"),
                    "closing_balance": (s.get("closingBalance") or {}).get("value"),
                }
                for s in statements[:12]
            ],
        }


class OVOLast3DaysSensor(OVOBaseSensor):
    """Last 3 days of grid usage — total kWh as state, per-day detail in attributes.

    Surfaces coordinator.data["last_3_days"], which was computed every refresh but
    previously had no entity (orphan analytics, same class as #74).
    """

    def __init__(self, coordinator):
        super().__init__(
            coordinator, "last_3_days_grid", "Grid Consumption (Last 3 Days)", "Last 3 Days"
        )
        self._attr_icon = "mdi:calendar-range"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        days = self.coordinator.data.get("last_3_days") or []
        if not days:
            return None
        return round(sum(d.get("grid_consumption", 0) or 0 for d in days), 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        days = self.coordinator.data.get("last_3_days") or []
        return {"days": days, "day_count": len(days)}


class OVOEnergyDashboardSensor(OVOBaseSensor):
    """Cumulative month-to-date energy sensor for HA's built-in Energy Dashboard (#73).

    OVO exposes period totals, not a raw meter reading, so this uses
    state_class=TOTAL with last_reset at the start of the source data month — the
    pattern Home Assistant expects for period-based sources. The monthly
    grid/export/solar aggregate accumulates through the month and resets on the
    source month boundary (signalled via last_reset). OVO data is delayed, so
    changes are recorded when fetched, not backdated to the consumption hour.
    Add these under Settings -> Energy.
    """

    def __init__(self, coordinator, key, name, data_key, icon):
        super().__init__(coordinator, key, name, "Energy Dashboard")
        self._data_key = data_key
        self._icon = icon
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def icon(self) -> str:
        return self._icon

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        if self.last_reset is None:
            return None
        val = (self.coordinator.data.get("monthly") or {}).get(self._data_key)
        return round(float(val), 3) if val is not None else None

    @property
    def last_reset(self) -> datetime | None:
        """Reset only when the source total moves to a new published month.

        OVO can still return the previous month after local midnight. Changing
        the reset while retaining that total would count it a second time.
        """
        monthly = (self.coordinator.data or {}).get("monthly") or {}
        source = "solar_latest" if self._data_key == "solar_consumption" else "grid_latest"
        timestamp = parse_ovo_datetime((monthly.get(source) or {}).get("periodFrom"))
        if timestamp is None:
            return None
        return timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class OVOLatestPaymentSensor(OVOBaseSensor):
    """Most recent payment — amount as state, date/type/history in attributes."""

    def __init__(self, coordinator):
        super().__init__(coordinator, "latest_payment", "Latest Payment", "Payments")
        self._attr_icon = "mdi:cash-register"
        self._attr_native_unit_of_measurement = "AUD"
        self._attr_device_class = SensorDeviceClass.MONETARY

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        amt = (self.coordinator.data.get("latest_payment") or {}).get("amount")
        return round(float(amt), 2) if amt is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        lp = self.coordinator.data.get("latest_payment") or {}
        payments = self.coordinator.data.get("payments") or []
        return {
            "date": lp.get("date"),
            "payment_type": lp.get("type"),
            "payment_count": len(payments),
            "recent_payments": payments[:12],
        }


class OVOReferralSensor(OVOBaseSensor):
    """Refer-a-friend earnings — total earned as state, code/count in attributes."""

    def __init__(self, coordinator):
        super().__init__(coordinator, "referral_earnings", "Referral Earnings", "Referrals")
        self._attr_icon = "mdi:account-multiple-plus"
        self._attr_native_unit_of_measurement = "AUD"
        self._attr_device_class = SensorDeviceClass.MONETARY

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        earned = (self.coordinator.data.get("referral") or {}).get("total_earned")
        return round(float(earned), 2) if earned is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        ref = self.coordinator.data.get("referral") or {}
        return {
            "referral_code": ref.get("code"),
            "referrals": ref.get("referral_count"),
        }


class OVOFlexSensor(OVOBaseSensor):
    """OVO Flex onboarding status (diagnostic).

    The OVO API's `flex` object exposes a single field, `hasOnboarded` — there is
    no balance/credits/VPP data in the API (confirmed by scanning the web app's
    GraphQL operations). GetNotificationInfo is intentionally not surfaced: its
    input requires an `fcmToken` (a mobile push token) that an HA integration
    does not have.
    """

    def __init__(self, coordinator):
        super().__init__(coordinator, "flex_onboarded", "OVO Flex Onboarded", "General")
        self._attr_icon = "mdi:account-star"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        onboarded = (self.coordinator.data.get("flex") or {}).get("onboarded")
        if onboarded is None:
            return None
        return "Onboarded" if onboarded else "Not Onboarded"
