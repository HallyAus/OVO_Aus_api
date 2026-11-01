"""Shared coordinator and clock behaviour for live tariff entities."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .tariffs import get_current_product, get_tariff_details


class OVOTariffEntity(CoordinatorEntity):
    """Platform-neutral tariff entity updated by both data and the local clock.

    Do not inherit SensorEntity here: binary sensors must resolve their state
    through BinarySensorEntity.is_on, not SensorEntity.native_value.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.account_id}_{key}"
        self._attr_name = name

    async def async_added_to_hass(self) -> None:
        """Publish whole-hour tariff transitions without polling the OVO API."""
        await super().async_added_to_hass()
        # Every supported tariff boundary is a whole customer-local hour.
        # HA's local scheduler handles DST and half-hour zones such as Adelaide.
        # Register per entity so disabling/removing one also removes its timer.
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._async_tariff_time_changed, minute=0, second=0
            )
        )

    @callback
    def _async_tariff_time_changed(self, _now: datetime) -> None:
        """Re-evaluate from the current clock, including after a delayed callback."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Keep unavailable/missing auto-detected tariffs unavailable on clock ticks."""
        if (
            getattr(self.coordinator, "auto_detect_plan", False) is True
            and not get_current_product(self.coordinator.data)
        ):
            return False
        return bool(getattr(self.coordinator, "last_update_success", True))

    def _period_details(self, now: datetime | None = None) -> dict[str, Any]:
        """Resolve the tariff in HA's configured customer-local timezone.

        A Sydney installation uses Australia/Sydney, including daylight saving.
        Forcing Sydney here would reintroduce the interstate regression in #86.
        The host operating system's timezone is not used by dt_util.now().
        """
        local_now = now if now is not None else dt_util.now()
        return get_tariff_details(
            self.coordinator.plan_config, self.coordinator.data, local_now.hour
        )

    @property
    def device_info(self) -> dict[str, Any]:
        """Keep the existing tariff entity identities on the account device."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.account_id)},
            "name": "OVO Energy AU",
            "manufacturer": "OVO Energy Australia",
            "model": "Energy Monitor",
        }
