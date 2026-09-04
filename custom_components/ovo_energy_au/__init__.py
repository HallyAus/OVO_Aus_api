"""The OVO Energy Australia integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OVOEnergyAUApiClient, OVOEnergyAUApiClientAuthenticationError, OVOEnergyAUApiClientError
from .const import (
    CONF_ACCOUNT_ID,
    CONF_PEAK_END_HOUR,
    CONF_PEAK_START_HOUR,
    CONF_PLAN_TYPE,
    DOMAIN,
    PLAN_ONE,
)
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
    except OVOEnergyAUApiClientAuthenticationError:
        raise ConfigEntryAuthFailed("OVO authentication was rejected") from None
    except (OVOEnergyAUApiClientError, TimeoutError):
        raise ConfigEntryNotReady("Unable to reach OVO during setup") from None

    # Authentication remains in entry.data; user-adjustable plan settings live
    # in entry.options. The merge keeps existing pre-migration entries working.
    merged_config = {**entry.data, **entry.options}
    if (
        entry.options.get(CONF_PLAN_TYPE) == PLAN_ONE
        and CONF_PEAK_START_HOUR not in entry.options
        and CONF_PEAK_END_HOUR not in entry.options
    ):
        # A switch from a TOU product to a flat One Plan must not inherit the
        # previous plan's schedule from immutable entry.data.
        merged_config.pop(CONF_PEAK_START_HOUR, None)
        merged_config.pop(CONF_PEAK_END_HOUR, None)
    plan_config = PlanConfig.from_dict(merged_config)

    coordinator = OVOEnergyAUDataUpdateCoordinator(
        hass,
        client=client,
        account_id=account_id,
        plan_config=plan_config,
        auto_detect_plan=CONF_PLAN_TYPE not in entry.options,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Category and vehicle devices refer to this account by ``via_device_id``.
    # Create it before platforms add any child entities so HA never has to
    # resolve a missing parent (#77).
    account_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, account_id)},
        name="OVO Energy AU",
        manufacturer="OVO Energy Australia",
        model="Energy Monitor",
    )
    coordinator.account_device_id = account_device.id
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
