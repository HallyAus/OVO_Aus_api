"""Vehicle entities backed by the read-only Kaluza data source."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
)
from homeassistant.helpers.entity import EntityCategory

from ..const import AU_TIMEZONE, DOMAIN
from .base import OVOBaseSensor


def _get_path(data: dict[str, Any], path: str) -> Any:
    value: Any = data
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _next_charge_interval(vehicle: dict[str, Any]) -> dict[str, Any] | None:
    intervals = (vehicle.get("charge_plan") or {}).get("intervals") or []
    now = datetime.now(UTC)
    candidates = []
    for interval in intervals:
        if not isinstance(interval, dict):
            continue
        end = _parse_timestamp(interval.get("end"))
        if end is None or end >= now:
            candidates.append(interval)
    charging = [item for item in candidates if item.get("should_charge") is True]
    return (charging or candidates or [None])[0]


VEHICLE_SENSOR_DEFINITIONS = [
    ("battery_soc", "Battery", "battery_soc_percent", PERCENTAGE,
     SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, "mdi:car-electric"),
    ("estimated_range", "Estimated Range", "estimated_range_km", UnitOfLength.KILOMETERS,
     SensorDeviceClass.DISTANCE, SensorStateClass.MEASUREMENT, "mdi:map-marker-distance"),
    ("cable_state", "Cable State", "cable_state", None,
     None, None, "mdi:ev-plug-type2"),
    ("charge_limit", "Charge Limit", "charge_limit_percent", PERCENTAGE,
     None, SensorStateClass.MEASUREMENT, "mdi:battery-lock"),
    ("mode", "Charging Mode", "mode", None,
     None, None, "mdi:ev-station"),
    ("boosting", "Boosting", "is_boosting", None,
     None, None, "mdi:rocket-launch"),
    ("estimated_charge_start", "Estimated Charge Start", "estimated_charge_start", None,
     SensorDeviceClass.TIMESTAMP, None, "mdi:clock-start"),
    ("telemetry_updated", "Telemetry Updated", "telemetry_updated_at", None,
     SensorDeviceClass.TIMESTAMP, None, "mdi:update"),
    ("battery_capacity", "Battery Capacity", "battery_capacity_kwh", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, SensorStateClass.MEASUREMENT, "mdi:battery-high"),
    ("maximum_charge_power", "Maximum Charge Power", "preferences.maximum_charge_power_w",
     UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:flash"),
    ("minimum_charge_power", "Minimum Charge Power", "preferences.minimum_charge_power_w",
     UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:flash-outline"),
    ("minimum_soc", "Minimum State of Charge", "preferences.minimum_soc_percent", PERCENTAGE,
     None, SensorStateClass.MEASUREMENT, "mdi:battery-arrow-down"),
    ("maximum_soc", "Maximum State of Charge", "preferences.maximum_soc_percent", PERCENTAGE,
     None, SensorStateClass.MEASUREMENT, "mdi:battery-arrow-up"),
    ("monthly_energy", "Charging Energy This Month", "monthly_energy.kwh",
     UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL,
     "mdi:ev-station"),
    ("monthly_cost", "Charging Cost This Month", "monthly_energy.cost_aud", "AUD",
     SensorDeviceClass.MONETARY, None, "mdi:cash"),
]


class OVOVehicleBaseSensor(OVOBaseSensor):
    """Base class that follows one vehicle across coordinator refreshes."""

    def __init__(self, coordinator, vehicle: dict[str, Any], key: str, name: str) -> None:
        super().__init__(coordinator, f"vehicle_{vehicle['id']}_{key}", name, "Vehicle")
        self._vehicle_id = vehicle["id"]

    @property
    def vehicle(self) -> dict[str, Any] | None:
        if not self.coordinator.data:
            return None
        return next(
            (
                item
                for item in self.coordinator.data.get("vehicles") or []
                if item.get("id") == self._vehicle_id
            ),
            None,
        )

    @property
    def available(self) -> bool:
        return (
            getattr(self.coordinator, "last_update_success", True)
            and self.vehicle is not None
        )

    @property
    def device_info(self) -> dict[str, Any]:
        vehicle = self.vehicle or {}
        return {
            "identifiers": {(DOMAIN, f"vehicle_{self._vehicle_id}")},
            "name": f"OVO {vehicle.get('name') or 'Electric Vehicle'}",
            "manufacturer": vehicle.get("make") or "OVO Energy Australia",
            "model": vehicle.get("model") or "Connected Vehicle",
            "via_device": (DOMAIN, self.coordinator.account_id),
        }


class OVOVehicleMetricSensor(OVOVehicleBaseSensor):
    """One automation-friendly vehicle measurement or state."""

    def __init__(self, coordinator, vehicle: dict[str, Any], definition) -> None:
        key, name, path, unit, device_class, state_class, icon = definition
        super().__init__(coordinator, vehicle, key, name)
        self._path = path
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_icon = icon

    @property
    def native_value(self) -> Any:
        vehicle = self.vehicle
        if not vehicle:
            return None
        value = _get_path(vehicle, self._path)
        if self._attr_device_class == SensorDeviceClass.TIMESTAMP:
            return _parse_timestamp(value)
        if isinstance(value, bool):
            return "On" if value else "Off"
        if isinstance(value, float):
            return round(value, 2)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self._sensor_key.endswith("_monthly_energy"):
            return dict((self.vehicle or {}).get("monthly_energy") or {})
        return {}

    @property
    def last_reset(self) -> datetime | None:
        if self._sensor_key.endswith("_monthly_energy"):
            now = datetime.now(AU_TIMEZONE)
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return None


class OVOVehicleStatusSensor(OVOVehicleBaseSensor):
    """Registration, readiness, integration, and vendor health."""

    def __init__(self, coordinator, vehicle: dict[str, Any]) -> None:
        super().__init__(coordinator, vehicle, "status", "Connection Status")
        self._attr_icon = "mdi:car-connected"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | None:
        return (self.vehicle or {}).get("status")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        vehicle = self.vehicle or {}
        return {
            "control_ready": vehicle.get("control_ready"),
            "integration": vehicle.get("integration"),
            "timezone": vehicle.get("timezone"),
            "certificate_installed": vehicle.get("certificate_installed"),
            "vehicle_updated_at": vehicle.get("vehicle_updated_at"),
        }


class OVOVehiclePreferencesSensor(OVOVehicleBaseSensor):
    """Complete privacy-safe charging preference view."""

    def __init__(self, coordinator, vehicle: dict[str, Any]) -> None:
        super().__init__(coordinator, vehicle, "preferences", "Charging Preferences")
        self._attr_icon = "mdi:tune-vertical"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self) -> str | None:
        return ((self.vehicle or {}).get("preferences") or {}).get("optimisation_type")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict((self.vehicle or {}).get("preferences") or {})


class OVOVehicleScheduleSensor(OVOVehicleBaseSensor):
    """Charging mode, demand-period flag, and tariff timing categories."""

    def __init__(self, coordinator, vehicle: dict[str, Any]) -> None:
        super().__init__(coordinator, vehicle, "schedule", "Charging Schedule")
        self._attr_icon = "mdi:calendar-clock"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self) -> str | None:
        return ((self.vehicle or {}).get("charging_times") or {}).get("mode")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict((self.vehicle or {}).get("charging_times") or {})


class OVOVehicleChargePlanSensor(OVOVehicleBaseSensor):
    """Current/future charge-plan decision with every returned interval."""

    def __init__(self, coordinator, vehicle: dict[str, Any]) -> None:
        super().__init__(coordinator, vehicle, "charge_plan", "Charge Plan")
        self._attr_icon = "mdi:timeline-clock"

    @property
    def native_value(self) -> str:
        vehicle = self.vehicle or {}
        interval = _next_charge_interval(vehicle)
        if not interval:
            return "Idle"
        start = _parse_timestamp(interval.get("start"))
        end = _parse_timestamp(interval.get("end"))
        now = datetime.now(UTC)
        if interval.get("should_charge") is True:
            if start and end and start <= now < end:
                return "Charging Window"
            return "Scheduled"
        return "Waiting"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        plan = dict((self.vehicle or {}).get("charge_plan") or {})
        plan["next_interval"] = _next_charge_interval(self.vehicle or {})
        return plan


def create_vehicle_sensors(coordinator, vehicle: dict[str, Any]) -> list[OVOBaseSensor]:
    """Create the complete entity set for one sanitized vehicle."""
    sensors: list[OVOBaseSensor] = [
        OVOVehicleMetricSensor(coordinator, vehicle, definition)
        for definition in VEHICLE_SENSOR_DEFINITIONS
    ]
    sensors.extend(
        [
            OVOVehicleStatusSensor(coordinator, vehicle),
            OVOVehiclePreferencesSensor(coordinator, vehicle),
            OVOVehicleScheduleSensor(coordinator, vehicle),
            OVOVehicleChargePlanSensor(coordinator, vehicle),
        ]
    )
    return sensors
