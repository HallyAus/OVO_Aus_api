"""OVO Energy Australia integration for Home Assistant."""
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_ACCESS_TOKEN,
    CONF_ID_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_REFRESH_TOKEN,
    DEFAULT_SCAN_INTERVAL,
)
from .ovo_client import OVOEnergyAU, OVOAPIError, OVOTokenExpiredError

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the OVO Energy Australia component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OVO Energy Australia from a config entry."""

    # Extract configuration
    access_token = entry.data.get(CONF_ACCESS_TOKEN)
    id_token = entry.data.get(CONF_ID_TOKEN)
    refresh_token = entry.data.get(CONF_REFRESH_TOKEN)
    account_id = entry.data.get(CONF_ACCOUNT_ID)

    # Define token update callback
    def token_update_callback(new_access_token: str, new_id_token: str, new_refresh_token: str):
        """Update config entry with new tokens."""
        _LOGGER.info("Updating config entry with refreshed tokens")
        hass.config_entries.async_update_entry(
            entry,
            data={
                CONF_ACCESS_TOKEN: new_access_token,
                CONF_ID_TOKEN: new_id_token,
                CONF_REFRESH_TOKEN: new_refresh_token,
                CONF_ACCOUNT_ID: account_id,
            },
        )

    # Create OVO client
    client = OVOEnergyAU(
        account_id=account_id,
        refresh_token=refresh_token,
        token_update_callback=token_update_callback
    )
    client.set_tokens(access_token, id_token, refresh_token)

    # Create update coordinator
    coordinator = OVODataUpdateCoordinator(
        hass,
        client=client,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.client.close()

    return unload_ok


class OVODataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching OVO Energy data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: OVOEnergyAU,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self):
        """Fetch data from OVO Energy API."""
        try:
            # Run sync client in executor
            data = await self.hass.async_add_executor_job(
                self.client.get_today_data
            )

            # Process and structure the data
            processed_data = self._process_data(data)

            _LOGGER.debug("Successfully updated OVO Energy data")
            return processed_data

        except OVOTokenExpiredError as err:
            _LOGGER.error(
                "OVO Energy tokens expired. Please update tokens in configuration. "
                "Tokens expire every 5 minutes."
            )
            raise UpdateFailed(f"Authentication failed: {err}") from err

        except OVOAPIError as err:
            _LOGGER.error("Error communicating with OVO Energy API: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        except Exception as err:
            _LOGGER.exception("Unexpected error fetching OVO Energy data")
            raise UpdateFailed(f"Unexpected error: {err}") from err

    def _process_data(self, raw_data: dict) -> dict:
        """Process raw API data into structured format for sensors."""
        solar_data = raw_data.get("solar", [])
        export_data = raw_data.get("export", [])
        savings_data = raw_data.get("savings", [])

        # Calculate totals for today
        solar_today = sum(point.get("consumption", 0) for point in solar_data)
        export_today = sum(point.get("consumption", 0) for point in export_data)

        # Savings uses amount.value structure
        savings_today = sum(
            point.get("amount", {}).get("value", 0) for point in savings_data
        )

        # Get current hour values (most recent data point)
        solar_current = solar_data[-1].get("consumption", 0) if solar_data else 0
        export_current = export_data[-1].get("consumption", 0) if export_data else 0

        return {
            "solar_current": solar_current,
            "export_current": export_current,
            "solar_today": solar_today,
            "export_today": export_today,
            "savings_today": savings_today,
            "last_updated": solar_data[-1].get("periodTo") if solar_data else None,
        }
