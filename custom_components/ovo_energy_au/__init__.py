"""The OVO Energy Australia integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OVOEnergyAUApiClient, OVOEnergyAUApiClientAuthenticationError
from .const import CONF_ACCOUNT_ID, DOMAIN
from .coordinator import OVOEnergyAUDataUpdateCoordinator
from .models import PlanConfig

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OVO Energy Australia from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    account_id = entry.data.get(CONF_ACCOUNT_ID)

    client = OVOEnergyAUApiClient(session, username=username, password=password)

    try:
        await client.authenticate_with_password(username, password)
        if not account_id:
            account_id = await client.get_account_id()
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_ACCOUNT_ID: account_id}
            )
    except OVOEnergyAUApiClientAuthenticationError as err:
        raise ConfigEntryAuthFailed(err) from err

    plan_config = PlanConfig.from_dict({
        "plan_type": entry.data.get("plan_type", "basic"),
        "peak_rate": entry.data.get("peak_rate", 0.35),
        "shoulder_rate": entry.data.get("shoulder_rate", 0.25),
        "off_peak_rate": entry.data.get("off_peak_rate", 0.18),
        "ev_rate": entry.data.get("ev_rate", 0.06),
        "flat_rate": entry.data.get("flat_rate", 0.28),
    })

    coordinator = OVOEnergyAUDataUpdateCoordinator(
        hass, client=client, account_id=account_id, plan_config=plan_config
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services only once
    if not hass.services.has_service(DOMAIN, "refresh_data"):
        async def handle_refresh_data(call: ServiceCall) -> None:
            """Handle manual refresh - refreshes all coordinators."""
            for _entry_id, coord in hass.data.get(DOMAIN, {}).items():
                await coord.async_request_refresh()

        hass.services.async_register(DOMAIN, "refresh_data", handle_refresh_data)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        # Clean up when last entry is removed
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "refresh_data")
            del hass.data[DOMAIN]
    return unload_ok
