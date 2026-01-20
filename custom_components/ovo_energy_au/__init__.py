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

from .api import OVOEnergyAUApiClient, OVOEnergyAUApiClientAuthenticationError
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

            # Get today's date for hourly data
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)

            # Fetch interval data (monthly/daily) and hourly data in parallel
            interval_data = await self.client.get_interval_data(self.account_id)
            hourly_data = await self.client.get_hourly_data(
                self.account_id,
                start_date=yesterday.isoformat(),
                end_date=today.isoformat()
            )

            _LOGGER.debug("Successfully fetched data from API")

            # Process and structure the data
            processed_data = self._process_data(interval_data, hourly_data)

            return processed_data

        except OVOEnergyAUApiClientAuthenticationError as err:
            _LOGGER.error("Authentication error: %s", err)
            raise ConfigEntryAuthFailed(err) from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching OVO Energy data")
            raise UpdateFailed(f"Error fetching data: {err}") from err

    def _process_data(self, interval_data: dict, hourly_data: dict) -> dict:
        """Process raw API data into structured format for sensors."""
        # Process hourly data for today
        solar_hourly = hourly_data.get("solar", [])
        export_hourly = hourly_data.get("export", [])

        # Calculate totals for today
        solar_today = sum(point.get("consumption", 0) for point in solar_hourly)
        export_today = sum(point.get("consumption", 0) for point in export_hourly)

        # Calculate savings for today (solar charge - export charge)
        solar_charge_today = sum(
            point.get("charge", {}).get("value", 0) for point in solar_hourly
        )
        export_charge_today = sum(
            point.get("charge", {}).get("value", 0) for point in export_hourly
        )
        savings_today = solar_charge_today - export_charge_today

        # Get current hour values (most recent data point)
        solar_current = solar_hourly[-1].get("consumption", 0) if solar_hourly else 0
        export_current = export_hourly[-1].get("consumption", 0) if export_hourly else 0

        # Process monthly interval data
        monthly_data = interval_data.get("monthly", {})
        monthly_solar = monthly_data.get("solar", [])
        monthly_export = monthly_data.get("export", [])

        # Get this month (last element) and last month (second-to-last)
        solar_this_month = monthly_solar[-1].get("consumption", 0) if monthly_solar else 0
        solar_last_month = monthly_solar[-2].get("consumption", 0) if len(monthly_solar) >= 2 else 0

        export_this_month = monthly_export[-1].get("consumption", 0) if monthly_export else 0
        export_last_month = monthly_export[-2].get("consumption", 0) if len(monthly_export) >= 2 else 0

        # Calculate monthly savings
        solar_charge_this_month = monthly_solar[-1].get("charge", {}).get("value", 0) if monthly_solar else 0
        solar_charge_last_month = monthly_solar[-2].get("charge", {}).get("value", 0) if len(monthly_solar) >= 2 else 0

        export_charge_this_month = monthly_export[-1].get("charge", {}).get("value", 0) if monthly_export else 0
        export_charge_last_month = monthly_export[-2].get("charge", {}).get("value", 0) if len(monthly_export) >= 2 else 0

        savings_this_month = solar_charge_this_month - export_charge_this_month
        savings_last_month = solar_charge_last_month - export_charge_last_month

        # Process daily interval data for day-by-day breakdown
        daily_data = interval_data.get("daily", {})
        daily_solar = daily_data.get("solar", [])
        daily_export = daily_data.get("export", [])

        # Get current month and last month for filtering
        now = datetime.now()
        current_month = now.month
        current_year = now.year

        # Calculate last month
        if current_month == 1:
            last_month = 12
            last_month_year = current_year - 1
        else:
            last_month = current_month - 1
            last_month_year = current_year

        # Filter daily data into this month and last month
        def filter_by_month(daily_list, month, year):
            """Filter daily data by month/year and format for attributes."""
            filtered = []
            for day in daily_list:
                period_from = day.get("periodFrom", "")
                if period_from:
                    try:
                        date = datetime.fromisoformat(period_from.replace("Z", "+00:00"))
                        if date.month == month and date.year == year:
                            filtered.append({
                                "date": date.strftime("%Y-%m-%d"),
                                "consumption": day.get("consumption", 0),
                                "charge": day.get("charge", {}).get("value", 0)
                            })
                    except Exception:
                        pass
            return sorted(filtered, key=lambda x: x["date"])

        # Create daily breakdowns
        solar_daily_this_month = filter_by_month(daily_solar, current_month, current_year)
        solar_daily_last_month = filter_by_month(daily_solar, last_month, last_month_year)

        export_daily_this_month = filter_by_month(daily_export, current_month, current_year)
        export_daily_last_month = filter_by_month(daily_export, last_month, last_month_year)

        # Calculate savings breakdowns
        savings_daily_this_month = [
            {
                "date": solar["date"],
                "savings": solar["charge"] - next(
                    (e["charge"] for e in export_daily_this_month if e["date"] == solar["date"]),
                    0
                )
            }
            for solar in solar_daily_this_month
        ]

        savings_daily_last_month = [
            {
                "date": solar["date"],
                "savings": solar["charge"] - next(
                    (e["charge"] for e in export_daily_last_month if e["date"] == solar["date"]),
                    0
                )
            }
            for solar in solar_daily_last_month
        ]

        return {
            "solar_current": solar_current,
            "export_current": export_current,
            "solar_today": solar_today,
            "export_today": export_today,
            "savings_today": savings_today,
            "solar_this_month": solar_this_month,
            "solar_last_month": solar_last_month,
            "export_this_month": export_this_month,
            "export_last_month": export_last_month,
            "savings_this_month": savings_this_month,
            "savings_last_month": savings_last_month,
            "solar_daily_this_month": solar_daily_this_month,
            "solar_daily_last_month": solar_daily_last_month,
            "export_daily_this_month": export_daily_this_month,
            "export_daily_last_month": export_daily_last_month,
            "savings_daily_this_month": savings_daily_this_month,
            "savings_daily_last_month": savings_daily_last_month,
            "last_updated": solar_hourly[-1].get("periodTo") if solar_hourly else None,
        }
