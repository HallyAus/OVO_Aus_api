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


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload an entry after its user-adjustable options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration-wide service actions."""

    async def handle_refresh_data(call: ServiceCall) -> None:
        """Refresh every loaded OVO config entry."""
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator = getattr(entry, "runtime_data", None)
            if coordinator is not None:
                await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "refresh_data", handle_refresh_data)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OVO Energy Australia from a config entry."""
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

    # Authentication remains in entry.data; user-adjustable plan settings live
    # in entry.options. The merge keeps existing pre-migration entries working.
    plan_config = PlanConfig.from_dict({**entry.data, **entry.options})

    coordinator = OVOEnergyAUDataUpdateCoordinator(
        hass, client=client, account_id=account_id, plan_config=plan_config
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
