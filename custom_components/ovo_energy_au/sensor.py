"""Sensor platform for OVO Energy Australia."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OVO Energy Australia sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        # Daily sensors
        OVOEnergyAUSensor(
            coordinator,
            "daily_solar_consumption",
            "Daily Solar Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:solar-power",
            lambda data: data.get("daily", {}).get("solar_consumption"),
        ),
        OVOEnergyAUSensor(
            coordinator,
            "daily_grid_consumption",
            "Daily Grid Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:transmission-tower",
            lambda data: data.get("daily", {}).get("grid_consumption"),
        ),
        OVOEnergyAUSensor(
            coordinator,
            "daily_return_to_grid",
            "Daily Return to Grid",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:transmission-tower-export",
            lambda data: data.get("daily", {}).get("return_to_grid"),
        ),
        OVOEnergyAUSensor(
            coordinator,
            "daily_solar_charge",
            "Daily Solar Charge",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("daily", {}).get("solar_charge"),
        ),
        OVOEnergyAUSensor(
            coordinator,
            "daily_grid_charge",
            "Daily Grid Charge",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("daily", {}).get("grid_charge"),
        ),
        OVOEnergyAUSensor(
            coordinator,
            "daily_return_to_grid_charge",
            "Daily Return to Grid Charge",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("daily", {}).get("return_to_grid_charge"),
        ),
        # Monthly sensors
        OVOEnergyAUSensor(
            coordinator,
            "monthly_solar_consumption",
            "Monthly Solar Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:solar-power",
            lambda data: data.get("monthly", {}).get("solar_consumption"),
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_grid_consumption",
            "Monthly Grid Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:transmission-tower",
            lambda data: data.get("monthly", {}).get("grid_consumption"),
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_return_to_grid",
            "Monthly Return to Grid",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:transmission-tower-export",
            lambda data: data.get("monthly", {}).get("return_to_grid"),
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_solar_charge",
            "Monthly Solar Charge",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("monthly", {}).get("solar_charge"),
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_grid_charge",
            "Monthly Grid Charge",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("monthly", {}).get("grid_charge"),
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_return_to_grid_charge",
            "Monthly Return to Grid Charge",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("monthly", {}).get("return_to_grid_charge"),
        ),
        # Yearly sensors
        OVOEnergyAUSensor(
            coordinator,
            "yearly_solar_consumption",
            "Yearly Solar Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:solar-power",
            lambda data: data.get("yearly", {}).get("solar_consumption"),
        ),
        OVOEnergyAUSensor(
            coordinator,
            "yearly_grid_consumption",
            "Yearly Grid Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:transmission-tower",
            lambda data: data.get("yearly", {}).get("grid_consumption"),
        ),
        OVOEnergyAUSensor(
            coordinator,
            "yearly_grid_charge",
            "Yearly Grid Charge",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("yearly", {}).get("grid_charge"),
        ),
        # Hourly totals
        OVOEnergyAUSensor(
            coordinator,
            "hourly_solar_consumption",
            "Hourly Solar Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            None,  # Not a total, just current value
            "mdi:solar-power",
            lambda data: data.get("hourly", {}).get("solar_total"),
        ),
        OVOEnergyAUSensor(
            coordinator,
            "hourly_grid_consumption",
            "Hourly Grid Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            None,  # Not a total, just current value
            "mdi:transmission-tower",
            lambda data: data.get("hourly", {}).get("grid_total"),
        ),
        OVOEnergyAUSensor(
            coordinator,
            "hourly_return_to_grid",
            "Hourly Return to Grid",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            None,  # Not a total, just current value
            "mdi:transmission-tower-export",
            lambda data: data.get("hourly", {}).get("return_to_grid_total"),
        ),
    ]

    async_add_entities(sensors)


class OVOEnergyAUSensor(CoordinatorEntity, SensorEntity):
    """Representation of an OVO Energy Australia sensor."""

    def __init__(
        self,
        coordinator,
        sensor_key: str,
        sensor_name: str,
        unit: str,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        icon: str,
        value_fn,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._sensor_name = sensor_name
        self._unit = unit
        self._device_class = device_class
        self._state_class = state_class
        self._icon = icon
        self._value_fn = value_fn

        # Generate unique ID
        self._attr_unique_id = f"{coordinator.account_id}_{sensor_key}"
        self._attr_has_entity_name = True

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._sensor_name

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            _LOGGER.debug("Sensor %s: coordinator.data is None", self._sensor_key)
            return None

        try:
            value = self._value_fn(self.coordinator.data)
            if value is None:
                _LOGGER.debug("Sensor %s: value_fn returned None", self._sensor_key)
                return None

            # Round to 2 decimal places
            rounded = round(float(value), 2)
            return rounded
        except Exception as err:
            _LOGGER.error(
                "Sensor %s: Error getting value: %s (data keys: %s)",
                self._sensor_key,
                err,
                list(self.coordinator.data.keys()) if self.coordinator.data else "None"
            )
            return None

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class."""
        return self._device_class

    @property
    def state_class(self) -> SensorStateClass | None:
        """Return the state class."""
        return self._state_class

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        if not self.coordinator.data:
            return {}

        attributes = {}

        # Add hourly entries for hourly sensors
        if "hourly_" in self._sensor_key:
            hourly_data = self.coordinator.data.get("hourly", {})

            if "solar" in self._sensor_key:
                entries = hourly_data.get("solar_entries", [])
                if entries:
                    attributes["entries"] = entries
                    attributes["entry_count"] = len(entries)
            elif "grid" in self._sensor_key:
                entries = hourly_data.get("grid_entries", [])
                if entries:
                    attributes["entries"] = entries
                    attributes["entry_count"] = len(entries)
            elif "return_to_grid" in self._sensor_key:
                entries = hourly_data.get("return_to_grid_entries", [])
                if entries:
                    attributes["entries"] = entries
                    attributes["entry_count"] = len(entries)

        # Add latest entry for daily/monthly/yearly sensors
        period = None
        if "daily_" in self._sensor_key:
            period = "daily"
        elif "monthly_" in self._sensor_key:
            period = "monthly"
        elif "yearly_" in self._sensor_key:
            period = "yearly"

        if period:
            period_data = self.coordinator.data.get(period, {})
            if "solar" in self._sensor_key and "solar_latest" in period_data:
                attributes["latest_entry"] = period_data["solar_latest"]
            elif ("grid" in self._sensor_key or "return" in self._sensor_key) and "grid_latest" in period_data:
                attributes["latest_entry"] = period_data["grid_latest"]

            # Add daily breakdown for monthly sensors
            if period == "monthly":
                # Solar consumption/charge daily breakdown
                if "solar" in self._sensor_key and "solar_daily_breakdown" in period_data:
                    breakdown = period_data["solar_daily_breakdown"]
                    attributes["daily_breakdown"] = breakdown
                    attributes["days_in_month"] = len(breakdown)

                    # Add statistics if available
                    if "solar_daily_avg" in period_data:
                        attributes["daily_average"] = period_data["solar_daily_avg"]
                    if "solar_daily_max" in period_data:
                        attributes["daily_max"] = period_data["solar_daily_max"]
                    if "solar_charge_daily_avg" in period_data:
                        attributes["daily_charge_average"] = period_data["solar_charge_daily_avg"]

                # Grid consumption/charge daily breakdown
                elif "grid" in self._sensor_key and "grid_daily_breakdown" in period_data:
                    breakdown = period_data["grid_daily_breakdown"]
                    attributes["daily_breakdown"] = breakdown
                    attributes["days_in_month"] = len(breakdown)

                # Return to grid daily breakdown
                elif "return" in self._sensor_key and "return_daily_breakdown" in period_data:
                    breakdown = period_data["return_daily_breakdown"]
                    attributes["daily_breakdown"] = breakdown
                    attributes["days_in_month"] = len(breakdown)

        return attributes

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.account_id)},
            "name": f"OVO Energy AU {self.coordinator.account_id}",
            "manufacturer": "OVO Energy Australia",
            "model": "Energy Monitor",
        }
