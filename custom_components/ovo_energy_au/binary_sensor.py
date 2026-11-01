"""Binary sensor platform for OVO Energy Australia."""
from __future__ import annotations

from datetime import time
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .tariff_entity import OVOTariffEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OVO Energy Australia binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities([OVOFreeEnergyWindowBinarySensor(coordinator)])


class OVOFreeEnergyWindowBinarySensor(OVOTariffEntity, BinarySensorEntity):
    """Binary sensor indicating whether the Free Energy window is currently active."""

    def __init__(self, coordinator):
        super().__init__(
            coordinator,
            "free_energy_window",
            "Free Energy Window",
        )

    @property
    def is_on(self) -> bool:
        """Return True if currently inside the free energy window."""
        details = self._period_details()
        # A zero ordinary rate does not make it the advertised free window.
        return details.get("current_period") == "Super Off-Peak (FREE)"

    @property
    def icon(self) -> str:
        """Return dynamic icon based on state."""
        return "mdi:gift" if self.is_on else "mdi:clock-time-four-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        now = dt_util.now()
        details = self._period_details(now)
        free_window = details.get("free_window")
        attrs: dict[str, Any] = {
            "plan_type": self.coordinator.plan_config.plan_type,
            "current_period": details.get("current_period"),
            "free_window": free_window,
            "next_period": details.get("next_period"),
            "next_period_change": details.get("next_period_change"),
        }
        if details.get("current_period") == "Super Off-Peak (FREE)" and free_window:
            # The schedule helper supplies same-day whole-hour free windows.
            # Retain minutes/seconds instead of reporting an hour at 13:59:59.
            end_time = time.fromisoformat(free_window.split("-")[1])
            end = now.replace(
                hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0
            )
            attrs["hours_remaining"] = max(0, (end - now).total_seconds() / 3600)
        return attrs
