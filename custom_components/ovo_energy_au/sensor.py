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

from .const import (
    DOMAIN,
    SENSOR_SOLAR_CURRENT,
    SENSOR_EXPORT_CURRENT,
    SENSOR_SOLAR_TODAY,
    SENSOR_EXPORT_TODAY,
    SENSOR_SAVINGS_TODAY,
    SENSOR_SOLAR_THIS_MONTH,
    SENSOR_SOLAR_LAST_MONTH,
    SENSOR_EXPORT_THIS_MONTH,
    SENSOR_EXPORT_LAST_MONTH,
    SENSOR_SAVINGS_THIS_MONTH,
    SENSOR_SAVINGS_LAST_MONTH,
    UNIT_KWH,
    UNIT_CURRENCY,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OVO Energy sensors based on a config entry."""
    _LOGGER.info("Setting up OVO Energy sensors for entry %s", entry.entry_id)

    coordinator = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.info("Coordinator found: %s, data: %s", coordinator, coordinator.data)

    # Define sensors
    sensors = [
        OVOEnergySensor(
            coordinator,
            SENSOR_SOLAR_CURRENT,
            "Solar Generation (Current Hour)",
            "mdi:solar-power",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.MEASUREMENT,
        ),
        OVOEnergySensor(
            coordinator,
            SENSOR_EXPORT_CURRENT,
            "Grid Export (Current Hour)",
            "mdi:transmission-tower-export",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.MEASUREMENT,
        ),
        OVOEnergySensor(
            coordinator,
            SENSOR_SOLAR_TODAY,
            "Solar Generation (Today)",
            "mdi:solar-power-variant",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL_INCREASING,
        ),
        OVOEnergySensor(
            coordinator,
            SENSOR_EXPORT_TODAY,
            "Grid Export (Today)",
            "mdi:transmission-tower",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL_INCREASING,
        ),
        OVOEnergySensor(
            coordinator,
            SENSOR_SAVINGS_TODAY,
            "Cost Savings (Today)",
            "mdi:currency-usd",
            UNIT_CURRENCY,
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
        ),
        OVOEnergySensor(
            coordinator,
            SENSOR_SOLAR_THIS_MONTH,
            "Solar Generation (This Month)",
            "mdi:solar-power-variant",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL_INCREASING,
        ),
        OVOEnergySensor(
            coordinator,
            SENSOR_SOLAR_LAST_MONTH,
            "Solar Generation (Last Month)",
            "mdi:solar-power-variant-outline",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
        ),
        OVOEnergySensor(
            coordinator,
            SENSOR_EXPORT_THIS_MONTH,
            "Grid Export (This Month)",
            "mdi:transmission-tower",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL_INCREASING,
        ),
        OVOEnergySensor(
            coordinator,
            SENSOR_EXPORT_LAST_MONTH,
            "Grid Export (Last Month)",
            "mdi:transmission-tower-off",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
        ),
        OVOEnergySensor(
            coordinator,
            SENSOR_SAVINGS_THIS_MONTH,
            "Cost Savings (This Month)",
            "mdi:currency-usd",
            UNIT_CURRENCY,
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
        ),
        OVOEnergySensor(
            coordinator,
            SENSOR_SAVINGS_LAST_MONTH,
            "Cost Savings (Last Month)",
            "mdi:currency-usd-off",
            UNIT_CURRENCY,
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
        ),
    ]

    _LOGGER.info("Adding %d OVO Energy sensors", len(sensors))
    async_add_entities(sensors)
    _LOGGER.info("OVO Energy sensors added successfully")


class OVOEnergySensor(CoordinatorEntity, SensorEntity):
    """Representation of an OVO Energy sensor."""

    def __init__(
        self,
        coordinator,
        sensor_type: str,
        name: str,
        icon: str,
        unit: str,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._sensor_type = sensor_type
        self._attr_name = f"OVO Energy {name}"
        self._attr_unique_id = f"ovo_energy_au_{sensor_type}"
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            _LOGGER.warning("Sensor %s: coordinator.data is None", self._sensor_type)
            return None

        value = self.coordinator.data.get(self._sensor_type)

        if value is None:
            _LOGGER.warning("Sensor %s: value is None, coordinator data: %s",
                          self._sensor_type, self.coordinator.data)
            return None

        # Round to 2 decimal places
        rounded = round(value, 2)
        _LOGGER.debug("Sensor %s: value = %s", self._sensor_type, rounded)
        return rounded

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if self.coordinator.data is None:
            return {}

        attributes = {
            "last_updated": self.coordinator.data.get("last_updated"),
        }

        # Add daily breakdown for monthly sensors
        daily_breakdown_map = {
            SENSOR_SOLAR_THIS_MONTH: "solar_daily_this_month",
            SENSOR_SOLAR_LAST_MONTH: "solar_daily_last_month",
            SENSOR_EXPORT_THIS_MONTH: "export_daily_this_month",
            SENSOR_EXPORT_LAST_MONTH: "export_daily_last_month",
            SENSOR_SAVINGS_THIS_MONTH: "savings_daily_this_month",
            SENSOR_SAVINGS_LAST_MONTH: "savings_daily_last_month",
        }

        if self._sensor_type in daily_breakdown_map:
            daily_key = daily_breakdown_map[self._sensor_type]
            daily_data = self.coordinator.data.get(daily_key, [])

            if daily_data:
                attributes["daily_breakdown"] = daily_data
                attributes["days_count"] = len(daily_data)

                # Add helpful summary stats
                if daily_data:
                    consumptions = [d.get("consumption", 0) for d in daily_data]
                    attributes["daily_average"] = round(sum(consumptions) / len(consumptions), 2) if consumptions else 0
                    attributes["daily_max"] = round(max(consumptions), 2) if consumptions else 0
                    attributes["daily_min"] = round(min(consumptions), 2) if consumptions else 0

        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None
