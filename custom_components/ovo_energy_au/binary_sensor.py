"""Binary sensor platform for OVO Energy Australia."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PLAN_FREE_3, PLAN_FREE_4
from .sensors.base import OVOBaseSensor
from .tariffs import get_current_product, get_tariff_details

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OVO Energy Australia binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities([OVOFreeEnergyWindowBinarySensor(coordinator)])


class OVOFreeEnergyWindowBinarySensor(OVOBaseSensor, BinarySensorEntity):
    """Binary sensor indicating whether the Free Energy window is currently active."""

    def __init__(self, coordinator):
        super().__init__(
            coordinator,
            "free_energy_window",
            "Free Energy Window",
            "Tariff",
        )

    @property
    def is_on(self) -> bool:
        """Return True if currently inside the free energy window."""
        details = self._period_details()
        return details.get("current_period") == "Super Off-Peak (FREE)" or (
            self.coordinator.plan_config.plan_type in (PLAN_FREE_3, PLAN_FREE_4)
            and details.get("rate_cents_kwh") == 0
        )

    @property
    def icon(self) -> str:
        """Return dynamic icon based on state."""
        return "mdi:gift" if self.is_on else "mdi:clock-time-four-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        details = self._period_details()
        hour = dt_util.now().hour
        free_window = details.get("free_window")
        attrs: dict[str, Any] = {
            "plan_type": self.coordinator.plan_config.plan_type,
            "current_period": details.get("current_period"),
            "free_window": free_window,
            "next_period": details.get("next_period"),
            "next_period_change": details.get("next_period_change"),
        }
        if self.is_on and free_window and "-" in free_window:
            try:
                start_str, end_str = free_window.split("-")
                end_hour = int(end_str.split(":")[0])
                attrs["hours_remaining"] = max(0, end_hour - hour)
            except Exception:
                pass
        return attrs

    @property
    def available(self) -> bool:
        if (
            getattr(self.coordinator, "auto_detect_plan", False) is True
            and not get_current_product(self.coordinator.data)
        ):
            return False
        return bool(getattr(self.coordinator, "last_update_success", True))

    def _period_details(self) -> dict:
        return get_tariff_details(
            self.coordinator.plan_config,
            self.coordinator.data,
            dt_util.now().hour,
        )

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.account_id)},
            "name": "OVO Energy AU",
            "manufacturer": "OVO Energy Australia",
            "model": "Energy Monitor",
        }
