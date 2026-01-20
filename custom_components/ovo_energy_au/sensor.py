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
    coordinator = hass.data[DOMAIN][entry.entry_id]

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
    ]

    async_add_entities(sensors)


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
            return None

        value = self.coordinator.data.get(self._sensor_type)

        if value is None:
            return None

        # Round to 2 decimal places
        return round(value, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if self.coordinator.data is None:
            return {}

        return {
            "last_updated": self.coordinator.data.get("last_updated"),
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None
