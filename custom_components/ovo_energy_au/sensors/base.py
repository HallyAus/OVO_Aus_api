"""Base sensor classes for OVO Energy Australia."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import AU_TIMEZONE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class OVOBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for all OVO Energy sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        sensor_key: str,
        sensor_name: str,
        device_category: str = "General",
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._sensor_name = sensor_name
        self._device_category = device_category
        self._attr_unique_id = f"{coordinator.account_id}_{sensor_key}"

    @property
    def name(self) -> str:
        return self._sensor_name

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, f"{self.coordinator.account_id}_{self._device_category}")},
            "name": f"OVO Energy AU - {self._device_category}",
            "manufacturer": "OVO Energy Australia",
            "model": "Energy Monitor",
            "via_device": (DOMAIN, self.coordinator.account_id),
        }


class OVOEnergySensor(OVOBaseSensor):
    """Generic sensor using a value extraction function."""

    def __init__(
        self,
        coordinator,
        sensor_key: str,
        sensor_name: str,
        unit: str | None,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        icon: str,
        value_fn,
        device_category: str = "General",
    ) -> None:
        super().__init__(coordinator, sensor_key, sensor_name, device_category)
        self._unit = unit
        self._device_class = device_class
        self._state_class = state_class
        self._icon = icon
        self._value_fn = value_fn

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        try:
            value = self._value_fn(self.coordinator.data)
            return round(float(value), 2) if value is not None else None
        except Exception as err:
            _LOGGER.debug("Sensor %s error: %s", self._sensor_key, err)
            return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self._unit

    @property
    def device_class(self) -> SensorDeviceClass | None:
        return self._device_class

    @property
    def state_class(self) -> SensorStateClass | None:
        return self._state_class

    @property
    def icon(self) -> str:
        return self._icon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes based on sensor category."""
        if not self.coordinator.data:
            return {}

        attrs = {}

        # Add week comparison details
        if "week_comparison" in self._sensor_key:
            week_data = self.coordinator.data.get("week_comparison", {})
            if week_data:
                attrs["all_metrics"] = week_data

        # Self-sufficiency details
        elif self._sensor_key == "self_sufficiency_score":
            ss = self.coordinator.data.get("self_sufficiency", {})
            if ss:
                attrs.update({k: v for k, v in ss.items() if k != "score"})

        # High usage days rankings
        elif self._sensor_key == "high_usage_days":
            high = self.coordinator.data.get("high_usage_days", [])
            if high:
                attrs["rankings"] = high
                attrs["rank_count"] = len(high)

        # Heatmap data
        elif self._sensor_key == "hourly_heatmap":
            heatmap = self.coordinator.data.get("hourly", {}).get("hourly_heatmap", {})
            if heatmap:
                attrs["heatmap_data"] = heatmap
                attrs["days_available"] = list(heatmap.keys())

        # Monthly projection details
        elif "monthly_projection" in self._sensor_key or self._sensor_key == "monthly_daily_average":
            proj = self.coordinator.data.get("monthly_projection", {})
            if proj:
                attrs.update(proj)

        # Cost per kWh details
        elif "cost_per_kwh" in self._sensor_key:
            cpk = self.coordinator.data.get("cost_per_kwh", {})
            if cpk:
                attrs.update(cpk)

        # Return-to-grid details
        elif "rtg_" in self._sensor_key:
            rtg = self.coordinator.data.get("return_to_grid_analysis", {})
            if rtg:
                attrs.update(rtg)

        # Yesterday hourly sensors - add hourly breakdown
        elif "_yesterday" in self._sensor_key and "hourly" in self._sensor_key:
            if "solar" in self._sensor_key:
                result = get_yesterday_hourly_data(self.coordinator.data, "solar_entries")
            elif "export" in self._sensor_key:
                result = get_yesterday_hourly_data(self.coordinator.data, "return_to_grid_entries")
            else:
                result = get_yesterday_hourly_data(self.coordinator.data, "grid_entries")
            attrs["hourly_values"] = result["hourly_data"]
            attrs["data_points"] = len(result["hourly_data"])

        # Monthly sensors - add daily breakdown
        elif "monthly_" in self._sensor_key:
            monthly = self.coordinator.data.get("monthly", {})
            if "solar" in self._sensor_key and "solar_daily_breakdown" in monthly:
                attrs["daily_breakdown"] = monthly["solar_daily_breakdown"]
            elif "grid" in self._sensor_key and "grid_daily_breakdown" in monthly:
                attrs["daily_breakdown"] = monthly["grid_daily_breakdown"]

        return attrs


# ─── Hourly data helpers ────────────────────────────────────────────


def parse_entry_timestamp(period_from: str) -> datetime | None:
    """Parse ISO timestamp and convert to Australian Eastern time."""
    if not period_from:
        return None
    try:
        ts = datetime.fromisoformat(period_from.replace("Z", "+00:00"))
        return ts.astimezone(AU_TIMEZONE)
    except (ValueError, TypeError):
        return None


def get_hourly_data_for_date(data: dict, entry_type: str, target_date) -> dict:
    """Get hourly data filtered to a specific date.

    Returns dict with 'state' (total kWh) and 'hourly_data' (list of hourly values).
    """
    if not data:
        return {"state": 0.0, "hourly_data": []}

    entries = data.get("hourly", {}).get(entry_type, [])
    if not entries:
        return {"state": 0.0, "hourly_data": []}

    hourly_values = []
    total = 0.0

    for entry in entries:
        ts = parse_entry_timestamp(entry.get("periodFrom", ""))
        if ts is None or ts.date() != target_date:
            continue

        consumption = entry.get("consumption", 0) or 0
        charge_info = entry.get("charge", {})
        charge_value = charge_info.get("value", 0) if isinstance(charge_info, dict) else 0
        charge_type = charge_info.get("type", "") if isinstance(charge_info, dict) else ""

        total += consumption
        hourly_values.append({
            "time": ts.isoformat(),
            "hour": ts.hour,
            "value": round(consumption, 3),
            "charge": round(abs(charge_value), 4) if charge_value else 0,
            "charge_type": charge_type,
        })

    hourly_values.sort(key=lambda x: x["hour"])
    return {"state": round(total, 2), "hourly_data": hourly_values}


def get_yesterday_hourly_data(data: dict, entry_type: str) -> dict:
    """Get yesterday's hourly data (in Australian Eastern time)."""
    yesterday = (datetime.now(AU_TIMEZONE) - timedelta(days=1)).date()
    return get_hourly_data_for_date(data, entry_type, yesterday)
