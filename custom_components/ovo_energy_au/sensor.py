"""Sensor platform for OVO Energy Australia.

This file is the HA entry point. It assembles sensors from definitions
and specialized classes, keeping the registration logic separate from
the sensor business logic.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .sensors.base import (
    AU_TIMEZONE,
    OVOBaseSensor,
    OVOEnergySensor,
    get_hourly_data_for_date,
)
from .sensors.definitions import (
    ANALYTICS_SENSORS,
    ENERGY_SENSORS,
    RATE_TYPE_ICONS,
    RATE_TYPES,
    calculate_free_savings,
    get_rate_value,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OVO Energy Australia sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
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

    # ── Dynamic per-day sensors ──
    _add_dynamic_day_sensors(sensors, coordinator)

    # ── Per-day hourly breakdown ──
    _add_hourly_day_sensors(sensors, coordinator)

    # ── Per-hour yesterday sensors ── (removed: data available in hourly day sensor attributes)

    # ── Plan diagnostic sensor ──
    sensors.append(OVOPlanSensor(coordinator))

    # ── Integration health diagnostic sensor ──
    sensors.append(OVOHealthSensor(coordinator))

    async_add_entities(sensors)


# ─── Sensor factory helpers ──────────────────────────────────────────


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


def _add_dynamic_day_sensors(sensors: list, coordinator) -> None:
    """Add per-day sensors for the last 7 days."""
    # Always create 7 day sensors regardless of initial data availability
    for idx in range(7):
        day_num = idx + 1
        for key, name, unit, dc, sc, icon in [
            ("solar_consumption", "Solar Consumption", UnitOfEnergy.KILO_WATT_HOUR,
             SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, "mdi:solar-power"),
            ("solar_charge", "Solar Feed-in Credit", "AUD",
             SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "mdi:cash-plus"),
            ("grid_consumption", "Grid Consumption", UnitOfEnergy.KILO_WATT_HOUR,
             SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, "mdi:transmission-tower"),
            ("grid_charge", "Grid Charge", "AUD",
             SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "mdi:currency-usd"),
        ]:
            sensors.append(OVODaySensor(
                coordinator, f"day_{day_num}_{key}", name, unit, dc, sc, icon, idx, key
            ))

        # Per-rate breakdown for this day
        for rate_type in RATE_TYPES:
            sensors.append(OVODayRateSensor(
                coordinator, f"day_{day_num}_grid_rate_{rate_type.lower()}_consumption",
                f"{rate_type.replace('_', ' ').title()} Consumption",
                UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL,
                RATE_TYPE_ICONS.get(rate_type, "mdi:flash"), idx, rate_type, "grid_rates_kwh",
            ))
            is_free = rate_type == "FREE_3"
            sensors.append(OVODayRateSensor(
                coordinator, f"day_{day_num}_grid_rate_{rate_type.lower()}_charge",
                f"{rate_type.replace('_', ' ').title()} {'Savings' if is_free else 'Cost'}",
                "AUD", SensorDeviceClass.MONETARY, SensorStateClass.TOTAL,
                "mdi:piggy-bank" if is_free else "mdi:currency-usd",
                idx, rate_type, "grid_rates_aud",
            ))

    # History sensors - always create 7
    for idx in range(7):
        sensors.append(OVODailyHistorySensor(
            coordinator, f"history_day_{idx}_total",
            f"Day {idx + 1} Total Consumption", idx, None, "mdi:calendar-today",
        ))
        for rate_type in ["EV_OFFPEAK", "FREE_3", "OTHER"]:
            sensors.append(OVODailyHistorySensor(
                coordinator, f"history_day_{idx}_{rate_type.lower()}",
                f"Day {idx + 1} {rate_type.replace('_', ' ').title()}",
                idx, rate_type, RATE_TYPE_ICONS.get(rate_type, "mdi:flash"),
            ))


def _add_hourly_day_sensors(sensors: list, coordinator) -> None:
    """Add per-day hourly breakdown sensors (last 7 days).

    Uses days_ago instead of fixed target_date so sensors compute
    the correct date dynamically on each update (survives midnight).
    """
    for days_ago in range(1, 8):
        for entry_type, type_label, icon in [
            ("solar_entries", "Solar", "mdi:solar-power"),
            ("grid_entries", "Grid", "mdi:transmission-tower"),
            ("return_to_grid_entries", "Export", "mdi:transmission-tower-export"),
        ]:
            sensors.append(OVOHourlyDaySensor(
                coordinator, f"hourly_{type_label.lower()}_{days_ago}d_ago",
                f"{type_label} Hourly {days_ago}d Ago",
                entry_type, days_ago, icon, f"Hourly {type_label}",
            ))


def _format_date_label(date_str: str) -> str:
    """Format 'YYYY-MM-DD' to 'Mon 20 Mar'."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%a %d %b")
    except (ValueError, TypeError):
        return date_str


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


class OVODaySensor(OVOBaseSensor):
    """Dynamic day sensor for last 7 days."""

    def __init__(self, coordinator, key, name, unit, device_class, state_class, icon, day_index, value_key):
        super().__init__(coordinator, key, name, "3 Day Snapshot")
        self._unit = unit
        self._device_class = device_class
        self._state_class = state_class
        self._icon = icon
        self._day_index = day_index
        self._value_key = value_key

    @property
    def name(self) -> str:
        if not self.coordinator.data:
            return self._sensor_name
        all_daily = self.coordinator.data.get("all_daily_entries", [])
        if self._day_index < len(all_daily):
            d = all_daily[self._day_index]
            label = _format_date_label(d.get("date", ""))
            day_name = d.get("day_name", "")
            if day_name:
                return f"{day_name} {label.split(' ', 1)[1] if ' ' in label else label}"
        return self._sensor_name

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        all_daily = self.coordinator.data.get("all_daily_entries", [])
        if self._day_index < len(all_daily):
            value = all_daily[self._day_index].get(self._value_key, 0)
            return round(float(value), 2) if value is not None else None
        return None

    @property
    def native_unit_of_measurement(self): return self._unit
    @property
    def device_class(self): return self._device_class
    @property
    def state_class(self): return self._state_class
    @property
    def icon(self): return self._icon


class OVODayRateSensor(OVOBaseSensor):
    """Per-rate sensor for a specific day."""

    def __init__(self, coordinator, key, name, unit, device_class, state_class, icon, day_index, rate_type, metric_key):
        super().__init__(coordinator, key, name, "3 Day Snapshot")
        self._unit = unit
        self._device_class = device_class
        self._state_class = state_class
        self._icon = icon
        self._day_index = day_index
        self._rate_type = rate_type
        self._metric_key = metric_key

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        all_daily = self.coordinator.data.get("all_daily_entries", [])
        if self._day_index >= len(all_daily):
            return 0
        day_data = all_daily[self._day_index]
        if self._rate_type == "FREE_3" and self._metric_key == "grid_rates_aud":
            return self._free3_savings(day_data)
        return round(float(day_data.get(self._metric_key, {}).get(self._rate_type, 0)), 2)

    def _free3_savings(self, day_data: dict) -> float:
        kwh = day_data.get("grid_rates_kwh", {}).get("FREE_3", 0)
        if kwh <= 0:
            return 0
        other_kwh = day_data.get("grid_rates_kwh", {}).get("OTHER", 0)
        other_aud = day_data.get("grid_rates_aud", {}).get("OTHER", 0)
        rate = (other_aud / other_kwh) if other_kwh > 0 else self.coordinator.plan_config.shoulder_rate
        return round(kwh * rate, 2)

    @property
    def native_unit_of_measurement(self): return self._unit
    @property
    def device_class(self): return self._device_class
    @property
    def state_class(self): return self._state_class
    @property
    def icon(self): return self._icon


class OVODailyHistorySensor(OVOBaseSensor):
    """History sensor showing a day's consumption by rate type."""

    def __init__(self, coordinator, key, name, day_index, rate_type, icon):
        super().__init__(coordinator, key, name, "Daily History")
        self._day_index = day_index
        self._rate_type = rate_type
        self._icon = icon
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        all_daily = self.coordinator.data.get("all_daily_entries", [])
        if self._day_index >= len(all_daily):
            return None
        day = all_daily[self._day_index]
        if self._rate_type is None:
            return round(day.get("grid_consumption", 0) + day.get("solar_consumption", 0), 2)
        return round(day.get("grid_rates_kwh", {}).get(self._rate_type, 0), 2)

    @property
    def icon(self): return self._icon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        all_daily = self.coordinator.data.get("all_daily_entries", [])
        if self._day_index >= len(all_daily):
            return {}
        day = all_daily[self._day_index]
        attrs = {
            "date": day.get("date"),
            "day_name": day.get("day_name"),
        }
        if self._rate_type is None:
            attrs["solar"] = round(day.get("solar_consumption", 0), 2)
            attrs["grid"] = round(day.get("grid_consumption", 0), 2)
            attrs["export"] = round(day.get("return_to_grid", 0), 2)
        return attrs


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
        agreements = pa.get("productAgreements", [])
        if not agreements:
            return "No Plan"
        return agreements[0].get("product", {}).get("displayName", "Unknown Plan")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        pa = self.coordinator.data.get("product_agreements")
        if not pa:
            return {"status": "No plan data available"}
        agreements = pa.get("productAgreements", [])
        if not agreements:
            return {"status": "No product agreements found"}

        agreement = agreements[0]
        product = agreement.get("product", {})
        unit_rates = product.get("unitRatesCentsPerKWH", {})

        attrs = {
            "account_id": pa.get("id", "Unknown"),
            "plan_name": product.get("displayName", "Unknown"),
            "product_code": product.get("code", "Unknown"),
            "nmi": agreement.get("nmi", "Unknown"),
            "from_date": agreement.get("fromDt", "Unknown"),
            "to_date": agreement.get("toDt", "Unknown"),
        }

        standing = product.get("standingChargeCentsPerDay", 0)
        if standing:
            attrs["standing_charge_cents_per_day"] = standing
            attrs["standing_charge_aud_per_day"] = round(standing / 100, 2)

        rate_fields = [
            ("peak", "peak"), ("shoulder", "shoulder"), ("offPeak", "off_peak"),
            ("evOffPeak", "ev_off_peak"), ("superOffPeak", "super_off_peak"),
            ("standard", "standard"), ("feedInTariff", "feed_in_tariff"),
        ]
        for api_key, label in rate_fields:
            val = unit_rates.get(api_key)
            if val is not None:
                attrs[f"{label}_cents_kwh"] = val
                attrs[f"{label}_aud_kwh"] = round(val / 100, 4)

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
        return "OK"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = {
            "account_id": self.coordinator.account_id,
            "update_interval_minutes": 5,
            "plan_type": self.coordinator.plan_config.plan_type,
        }

        if self.coordinator.data:
            all_daily = self.coordinator.data.get("all_daily_entries", [])
            hourly = self.coordinator.data.get("hourly", {})

            attrs["daily_entries_available"] = len(all_daily)
            attrs["hourly_solar_entries"] = len(hourly.get("solar_entries", []))
            attrs["hourly_grid_entries"] = len(hourly.get("grid_entries", []))
            attrs["has_product_agreements"] = self.coordinator.data.get("product_agreements") is not None

            if all_daily:
                attrs["oldest_daily_date"] = all_daily[-1].get("date")
                attrs["newest_daily_date"] = all_daily[0].get("date")

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


class OVOHourlyDaySensor(OVOBaseSensor):
    """Per-day hourly breakdown sensor.

    Uses days_ago to compute target_date dynamically on each update,
    so it survives midnight without needing an HA restart.
    Note: Hourly data from OVO is only available the next day after ~8am.
    """

    def __init__(self, coordinator, key, name, entry_type, days_ago, icon, category):
        super().__init__(coordinator, key, name, category)
        self._entry_type = entry_type
        self._days_ago = days_ago
        self._icon = icon
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL

    def _get_target_date(self):
        """Compute target date dynamically (survives midnight)."""
        return (datetime.now(AU_TIMEZONE) - timedelta(days=self._days_ago)).date()

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        result = get_hourly_data_for_date(
            self.coordinator.data, self._entry_type, self._get_target_date()
        )
        return result["state"] if result["state"] > 0 else 0.0

    @property
    def icon(self): return self._icon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        target = self._get_target_date()
        result = get_hourly_data_for_date(self.coordinator.data, self._entry_type, target)
        return {
            "date": target.isoformat(),
            "days_ago": self._days_ago,
            "hourly_values": result["hourly_data"],
            "data_points": len(result["hourly_data"]),
        }


