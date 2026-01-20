"""The OVO Energy Australia integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    OVOEnergyAUApiClient,
    OVOEnergyAUApiClientAuthenticationError,
    OVOEnergyAUApiClientCommunicationError,
    OVOEnergyAUApiClientError,
)
from .const import CONF_ACCOUNT_ID, DOMAIN, FAST_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OVO Energy Australia from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create API client
    session = async_get_clientsession(hass)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    account_id = entry.data.get(CONF_ACCOUNT_ID)

    client = OVOEnergyAUApiClient(session, username=username, password=password)

    # Authenticate on setup
    try:
        await client.authenticate_with_password(username, password)

        # Fetch account_id if not stored
        if not account_id:
            account_id = await client.get_account_id()
            # Update config entry with account_id
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_ACCOUNT_ID: account_id}
            )
    except OVOEnergyAUApiClientAuthenticationError as err:
        _LOGGER.error("Authentication failed during setup: %s", err)
        raise ConfigEntryAuthFailed(err) from err

    # Create coordinator
    coordinator = OVOEnergyAUDataUpdateCoordinator(
        hass,
        client=client,
        account_id=account_id,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    async def handle_refresh_data(call: ServiceCall) -> None:
        """Handle the refresh_data service call."""
        _LOGGER.info("Manual refresh requested via service call")
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "refresh_data", handle_refresh_data)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


class OVOEnergyAUDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching OVO Energy Australia data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: OVOEnergyAUApiClient,
        account_id: str,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.account_id = account_id

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=FAST_UPDATE_INTERVAL,
        )

    async def _async_update_data(self):
        """Fetch data from OVO Energy API."""
        try:
            _LOGGER.debug("Fetching data from OVO Energy API...")

            # Fetch interval data (daily/monthly/yearly)
            interval_data = await self.client.get_interval_data(self.account_id)
            processed_data = self._process_interval_data(interval_data)

            # Fetch hourly data for the last 7 days
            # This ensures we:
            # 1. Work around the API issue where single-day queries return 0 results
            # 2. Backfill recent history if the integration was offline
            # 3. Correctly update any partial data from previous days
            now = dt_util.now()

            # Query range: Last 7 days -> Today
            start_date = now - timedelta(days=7)
            query_start = start_date.strftime("%Y-%m-%d")
            query_end = now.strftime("%Y-%m-%d")

            try:
                hourly_data = await self.client.get_hourly_data(
                    self.account_id,
                    query_start,
                    query_end,
                )

                # Check if we got data
                has_solar = len(hourly_data.get("solar", []) or []) > 0
                has_export = len(hourly_data.get("export", []) or []) > 0

                if not has_solar and not has_export:
                    _LOGGER.info("No hourly data found in range %s to %s", query_start, query_end)
                else:
                    _LOGGER.debug(
                        "Successfully fetched hourly data (range query: %s to %s)",
                        query_start, query_end
                    )

                # Process hourly data
                processed_data["hourly"] = self._process_hourly_data(hourly_data)
            except Exception as err:
                _LOGGER.warning("Failed to fetch hourly data: %s", err)
                processed_data["hourly"] = {}

            _LOGGER.debug("Successfully processed all data")
            return processed_data

        except OVOEnergyAUApiClientAuthenticationError as err:
            _LOGGER.error("Authentication error: %s", err)
            raise ConfigEntryAuthFailed(err) from err
        except OVOEnergyAUApiClientCommunicationError as err:
            _LOGGER.error("Communication error: %s", err)
            raise UpdateFailed(f"Communication error: {err}") from err
        except OVOEnergyAUApiClientError as err:
            _LOGGER.error("API error: %s", err)
            raise UpdateFailed(f"API error: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching OVO Energy data")
            raise UpdateFailed(f"Error fetching data: {err}") from err

    def _process_interval_data(self, data: dict) -> dict:
        """Process the interval data (daily/monthly/yearly).

        The API returns arrays of historical data:
        - daily: array of individual day entries (latest = most recent day)
        - monthly: array of individual month entries (latest = current month)
        - yearly: array of individual year entries (latest = current year)

        We only use the LATEST entry from each array.
        """
        processed = {
            "daily": {},
            "monthly": {},
            "yearly": {},
        }

        for period in ["daily", "monthly", "yearly"]:
            if period not in data:
                continue

            period_data = data[period]

            # Process solar data - use only the LATEST entry
            if "solar" in period_data and period_data["solar"]:
                latest_solar = period_data["solar"][-1]
                processed[period]["solar_consumption"] = latest_solar.get("consumption", 0)
                processed[period]["solar_charge"] = latest_solar.get("charge", {}).get("value", 0)
                processed[period]["solar_latest"] = latest_solar

            # Process export data - use only the LATEST entry
            if "export" in period_data and period_data["export"]:
                latest_export = period_data["export"][-1]

                charge_type = latest_export.get("charge", {}).get("type", "DEBIT")
                consumption = latest_export.get("consumption", 0)
                charge_value = latest_export.get("charge", {}).get("value", 0)

                # CREDIT means returning power to grid (solar export)
                # DEBIT, FREE, PEAK, OFF_PEAK mean consuming from grid
                if charge_type == "CREDIT":
                    processed[period]["grid_consumption"] = 0
                    processed[period]["grid_charge"] = 0
                    processed[period]["return_to_grid"] = consumption
                    processed[period]["return_to_grid_charge"] = charge_value
                else:
                    # Default to grid consumption for DEBIT, FREE, PEAK, OFF_PEAK
                    processed[period]["grid_consumption"] = consumption
                    processed[period]["grid_charge"] = charge_value
                    processed[period]["return_to_grid"] = 0
                    processed[period]["return_to_grid_charge"] = 0

                processed[period]["grid_latest"] = latest_export

        # Add daily breakdown for monthly period (for graphing)
        if "daily" in data and data["daily"]:
            daily_data = data["daily"]

            # Get current month for filtering
            now = dt_util.now()
            current_month = now.month
            current_year = now.year

            # Process solar daily breakdown
            solar_daily_breakdown = []
            if "solar" in daily_data and daily_data["solar"]:
                for entry in daily_data["solar"]:
                    period_from = entry.get("periodFrom", "")
                    if period_from:
                        try:
                            # Parse the date
                            from datetime import datetime
                            entry_date = datetime.fromisoformat(period_from.replace("Z", "+00:00"))

                            # Only include current month
                            if entry_date.month == current_month and entry_date.year == current_year:
                                solar_daily_breakdown.append({
                                    "date": entry_date.strftime("%Y-%m-%d"),
                                    "day": entry_date.day,
                                    "consumption": entry.get("consumption", 0),
                                    "charge": entry.get("charge", {}).get("value", 0),
                                    "read_type": entry.get("readType", ""),
                                })
                        except Exception as err:
                            _LOGGER.debug("Error parsing solar daily entry: %s", err)
                            continue

            # Process export daily breakdown
            grid_daily_breakdown = []
            return_daily_breakdown = []
            if "export" in daily_data and daily_data["export"]:
                for entry in daily_data["export"]:
                    period_from = entry.get("periodFrom", "")
                    if period_from:
                        try:
                            from datetime import datetime
                            entry_date = datetime.fromisoformat(period_from.replace("Z", "+00:00"))

                            # Only include current month
                            if entry_date.month == current_month and entry_date.year == current_year:
                                charge_type = entry.get("charge", {}).get("type", "DEBIT")
                                consumption = entry.get("consumption", 0)
                                charge_value = entry.get("charge", {}).get("value", 0)

                                daily_entry = {
                                    "date": entry_date.strftime("%Y-%m-%d"),
                                    "day": entry_date.day,
                                    "consumption": consumption,
                                    "charge": charge_value,
                                    "read_type": entry.get("readType", ""),
                                    "charge_type": charge_type,
                                }

                                # Separate into grid consumption vs return to grid
                                if charge_type == "CREDIT":
                                    return_daily_breakdown.append(daily_entry)
                                else:
                                    grid_daily_breakdown.append(daily_entry)
                        except Exception as err:
                            _LOGGER.debug("Error parsing export daily entry: %s", err)
                            continue

            # Add to monthly data
            processed["monthly"]["solar_daily_breakdown"] = sorted(solar_daily_breakdown, key=lambda x: x["date"])
            processed["monthly"]["grid_daily_breakdown"] = sorted(grid_daily_breakdown, key=lambda x: x["date"])
            processed["monthly"]["return_daily_breakdown"] = sorted(return_daily_breakdown, key=lambda x: x["date"])

            # Add summary statistics
            if solar_daily_breakdown:
                processed["monthly"]["solar_daily_avg"] = round(
                    sum(d["consumption"] for d in solar_daily_breakdown) / len(solar_daily_breakdown), 2
                )
                processed["monthly"]["solar_daily_max"] = round(
                    max(d["consumption"] for d in solar_daily_breakdown), 2
                )
                processed["monthly"]["solar_charge_daily_avg"] = round(
                    sum(d["charge"] for d in solar_daily_breakdown) / len(solar_daily_breakdown), 2
                )

        return processed

    def _process_hourly_data(self, data: dict) -> dict:
        """Process hourly data.

        Unlike interval data, we keep ALL hourly entries for graphing.
        """
        processed = {
            "solar_entries": [],
            "grid_entries": [],
            "return_to_grid_entries": [],
            "solar_total": 0,
            "grid_total": 0,
            "return_to_grid_total": 0,
        }

        raw_solar_count = len(data.get("solar", []) or [])
        raw_export_count = len(data.get("export", []) or [])
        _LOGGER.debug(
            "Processing hourly data: %d raw solar entries, %d raw export entries",
            raw_solar_count, raw_export_count
        )

        # Process solar entries
        for entry in data.get("solar", []) or []:
            processed["solar_entries"].append(entry)
            processed["solar_total"] += entry.get("consumption", 0)

        # Process export entries
        for entry in data.get("export", []) or []:
            charge_type = entry.get("charge", {}).get("type", "DEBIT")
            consumption = entry.get("consumption", 0)

            # CREDIT = returning to grid, otherwise grid consumption
            if charge_type == "CREDIT":
                processed["return_to_grid_entries"].append(entry)
                processed["return_to_grid_total"] += consumption
            else:
                processed["grid_entries"].append(entry)
                processed["grid_total"] += consumption

        _LOGGER.debug(
            "Processed hourly: %d solar, %d grid, %d return entries",
            len(processed["solar_entries"]),
            len(processed["grid_entries"]),
            len(processed["return_to_grid_entries"])
        )

        return processed
