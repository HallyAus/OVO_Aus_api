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

    # Get plan configuration from entry data
    plan_config = {
        "plan_type": entry.data.get("plan_type", "basic"),
        "peak_rate": entry.data.get("peak_rate", 0.35),
        "shoulder_rate": entry.data.get("shoulder_rate", 0.25),
        "off_peak_rate": entry.data.get("off_peak_rate", 0.18),
        "ev_rate": entry.data.get("ev_rate", 0.06),
        "flat_rate": entry.data.get("flat_rate", 0.28),
    }

    # Create coordinator
    coordinator = OVOEnergyAUDataUpdateCoordinator(
        hass,
        client=client,
        account_id=account_id,
        plan_config=plan_config,
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
        plan_config: dict = None,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.account_id = account_id
        self.plan_config = plan_config or {
            "plan_type": "basic",
            "peak_rate": 0.35,
            "shoulder_rate": 0.25,
            "off_peak_rate": 0.18,
            "ev_rate": 0.06,
            "flat_rate": 0.28,
        }

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=FAST_UPDATE_INTERVAL,
        )

    @staticmethod
    def analyze_plan_and_rates(hourly_data: dict) -> dict:
        """Analyze hourly data to detect plan type and actual rates.

        Returns dict with:
            - plan_type: detected plan ("ev", "free_3", "basic", "one")
            - confidence: detection confidence 0-100
            - rates: dict of detected rates
            - charge_types_found: list of unique charge types in data
        """
        result = {
            "plan_type": "basic",
            "confidence": 0,
            "rates": {
                "peak": 0.35,
                "shoulder": 0.25,
                "off_peak": 0.18,
                "ev": 0.06,
            },
            "charge_types_found": [],
        }

        if not hourly_data:
            return result

        # Collect all entries with charge information
        charge_types = set()
        rate_samples = {"peak": [], "shoulder": [], "off_peak": [], "free": []}

        for source in ["solar", "export"]:
            for entry in hourly_data.get(source, []) or []:
                charge = entry.get("charge", {})
                charge_type = charge.get("type", "")
                charge_value = abs(charge.get("value", 0))
                consumption = entry.get("consumption", 0)

                if charge_type:
                    charge_types.add(charge_type)

                # Calculate rate if we have both consumption and charge
                if consumption > 0 and charge_value > 0:
                    rate = charge_value / consumption

                    if charge_type == "PEAK":
                        rate_samples["peak"].append(rate)
                    elif charge_type == "OFF_PEAK":
                        rate_samples["off_peak"].append(rate)
                    elif charge_type in ["SHOULDER", "DEBIT"]:
                        rate_samples["shoulder"].append(rate)
                    elif charge_type == "FREE":
                        rate_samples["free"].append(0.0)

        result["charge_types_found"] = list(charge_types)

        # Calculate average rates
        for period, samples in rate_samples.items():
            if samples and period != "free":
                result["rates"][period] = round(sum(samples) / len(samples), 4)

        # Detect plan type based on charge types found
        has_free = "FREE" in charge_types
        has_peak = "PEAK" in charge_types
        has_off_peak = "OFF_PEAK" in charge_types

        if has_free and has_peak and has_off_peak:
            # Could be Free 3 or EV plan
            # Check if there are very low rates (< 0.10) which would indicate EV plan
            if rate_samples["off_peak"]:
                min_off_peak = min(rate_samples["off_peak"])
                if min_off_peak < 0.10:
                    result["plan_type"] = "ev"
                    result["confidence"] = 85
                    result["rates"]["ev"] = round(min_off_peak, 4)
                else:
                    result["plan_type"] = "free_3"
                    result["confidence"] = 80
            else:
                result["plan_type"] = "free_3"
                result["confidence"] = 70
        elif has_free:
            # Just free periods, likely Free 3
            result["plan_type"] = "free_3"
            result["confidence"] = 75
        elif has_peak and has_off_peak:
            # Standard TOU, basic plan
            result["plan_type"] = "basic"
            result["confidence"] = 90
        elif len(charge_types) <= 2 and "DEBIT" in charge_types:
            # Mostly DEBIT, might be flat rate One plan
            result["plan_type"] = "one"
            result["confidence"] = 60
            if rate_samples["shoulder"]:
                result["rates"]["flat"] = round(sum(rate_samples["shoulder"]) / len(rate_samples["shoulder"]), 4)
        else:
            # Not enough data, default to basic
            result["plan_type"] = "basic"
            result["confidence"] = 30

        return result

    async def _async_update_data(self):
        """Fetch data from OVO Energy API."""
        try:
            # Fetch interval data (daily/monthly/yearly)
            interval_data = await self.client.get_interval_data(self.account_id)
            processed_data = self._process_interval_data(interval_data)

            # Fetch product agreements (plan information)
            try:
                product_info = await self.client.get_product_agreements(self.account_id)
                processed_data["product_agreements"] = product_info
            except Exception as err:
                _LOGGER.error("Failed to fetch product agreements: %s", err, exc_info=True)
                processed_data["product_agreements"] = None

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
                if not hourly_data:
                    hourly_data = {}

                has_solar = len(hourly_data.get("solar", []) or []) > 0
                has_export = len(hourly_data.get("export", []) or []) > 0

                if not has_solar and not has_export:
                    _LOGGER.info("No hourly data found in range %s to %s", query_start, query_end)

                # Process hourly data
                processed_data["hourly"] = self._process_hourly_data(hourly_data)
            except Exception as err:
                _LOGGER.warning("Failed to fetch hourly data: %s", err)
                # Set empty hourly data with default values for all analytics
                processed_data["hourly"] = {
                    "solar_entries": [],
                    "grid_entries": [],
                    "return_to_grid_entries": [],
                    "solar_total": 0,
                    "grid_total": 0,
                    "return_to_grid_total": 0,
                    "peak_4hour_window": None,
                    "time_of_use": {
                        "peak": {"consumption": 0, "cost": 0, "hours": 0},
                        "shoulder": {"consumption": 0, "cost": 0, "hours": 0},
                        "off_peak": {"consumption": 0, "cost": 0, "hours": 0},
                    },
                    "free_usage": {"consumption": 0, "cost_saved": 0, "hours": 0},
                    "ev_usage": {"consumption": 0, "cost": 0, "cost_saved": 0, "hours": 0},
                    "ev_usage_weekly": {"consumption": 0, "cost": 0, "cost_saved": 0, "hours": 0},
                    "ev_usage_monthly": {"consumption": 0, "cost": 0, "cost_saved": 0, "hours": 0},
                    "ev_usage_yearly": {"consumption": 0, "cost": 0, "cost_saved": 0, "hours": 0},
                    "hourly_heatmap": {},
                }

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
        - daily: array of individual day entries (latest = most recent day, which is YESTERDAY)
        - monthly: array of individual month entries (latest = current month)
        - yearly: array of individual year entries (latest = current year)

        IMPORTANT: Daily data is only available at 6am for the PREVIOUS day.
        """
        processed = {
            "daily": {},
            "monthly": {},
            "yearly": {},
            "last_3_days": [],
            "last_7_days": {},
            "last_month": {},
            "month_to_date": {},
        }

        # Process daily, monthly, yearly periods
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

                # Extract rate breakdown from API (if available)
                rates_breakdown = {}
                try:
                    if "rates" in latest_export and isinstance(latest_export.get("rates"), list):
                        for rate_entry in latest_export["rates"]:
                            if not isinstance(rate_entry, dict):
                                _LOGGER.warning("%s: Malformed rate entry (not dict): %s", period, rate_entry)
                                continue

                            rate_type = rate_entry.get("type")
                            if not rate_type:
                                _LOGGER.warning("%s: Rate entry missing type: %s", period, rate_entry)
                                continue

                            consumption = rate_entry.get("consumption", 0)
                            charge_obj = rate_entry.get("charge", {})
                            charge_value = charge_obj.get("value", 0) if isinstance(charge_obj, dict) else 0
                            percent = rate_entry.get("percentOfTotal", 0)

                            rates_breakdown[rate_type] = {
                                "consumption": float(consumption),
                                "charge": abs(float(charge_value)),
                                "percent": round(float(percent) * 100, 2),
                                "available": True
                            }

                        # Validation: Check if rates sum to total
                        total_rate_consumption = sum(r["consumption"] for r in rates_breakdown.values())
                        total_consumption = latest_export.get("consumption", 0)

                        if abs(total_rate_consumption - total_consumption) > 0.1:
                            _LOGGER.warning(
                                "%s: Rate breakdown sum (%.2f kWh) != total (%.2f kWh). Diff: %.2f kWh",
                                period, total_rate_consumption, total_consumption,
                                abs(total_rate_consumption - total_consumption)
                            )

                except Exception as err:
                    _LOGGER.error("Error processing rate breakdown for %s: %s", period, err)
                    rates_breakdown = {}

                # Store rate breakdown
                processed[period]["rate_breakdown"] = rates_breakdown

        # All Time Aggregation (from all monthly data since plan began)
        all_time_rates = {}
        all_time_solar_consumption = 0
        all_time_solar_charge = 0
        months_included = 0
        earliest_date = None
        latest_date = None

        if "monthly" in data and data["monthly"]:
            all_monthly_entries = data["monthly"].get("export", [])

            for entry in all_monthly_entries:
                months_included += 1

                # Track date range
                period_from = entry.get("periodFrom")
                period_to = entry.get("periodTo")
                if period_from:
                    if not earliest_date or period_from < earliest_date:
                        earliest_date = period_from
                if period_to:
                    if not latest_date or period_to > latest_date:
                        latest_date = period_to

                # Aggregate rates
                rates = entry.get("rates", [])
                for rate_entry in rates:
                    if not isinstance(rate_entry, dict):
                        continue

                    rate_type = rate_entry.get("type")
                    if not rate_type:
                        continue

                    consumption = rate_entry.get("consumption", 0)
                    charge_obj = rate_entry.get("charge", {})
                    charge_value = charge_obj.get("value", 0) if isinstance(charge_obj, dict) else 0

                    if rate_type not in all_time_rates:
                        all_time_rates[rate_type] = {
                            "consumption": 0,
                            "charge": 0,
                            "available": True
                        }

                    all_time_rates[rate_type]["consumption"] += float(consumption)
                    all_time_rates[rate_type]["charge"] += abs(float(charge_value))

            # Aggregate solar data from all monthly entries
            all_monthly_solar = data["monthly"].get("solar", [])
            for solar_entry in all_monthly_solar:
                if isinstance(solar_entry, dict):
                    all_time_solar_consumption += solar_entry.get("consumption", 0)
                    charge_obj = solar_entry.get("charge", {})
                    if isinstance(charge_obj, dict):
                        all_time_solar_charge += abs(charge_obj.get("value", 0))

            # Store all-time data
            processed["all_time"] = {
                "rate_breakdown": all_time_rates,
                "solar_consumption": round(all_time_solar_consumption, 3),
                "solar_charge": round(all_time_solar_charge, 2),
                "periodFrom": earliest_date,
                "periodTo": latest_date,
                "months_included": months_included
            }
        else:
            processed["all_time"] = {
                "rate_breakdown": {},
                "solar_consumption": 0,
                "solar_charge": 0,
                "periodFrom": None,
                "periodTo": None,
                "months_included": 0
            }

        # Process daily arrays for historical data
        if "daily" in data and data["daily"]:
            daily_data = data["daily"]

            # Get dates for filtering
            now = dt_util.now()
            current_month = now.month
            current_year = now.year

            # Process last 3 days (most recent 3 entries from daily array)
            all_daily_entries = []

            # Combine solar and export data by date
            solar_entries = daily_data.get("solar", [])
            export_entries = daily_data.get("export", [])

            # DEBUG: Log export_entries structure
            _LOGGER.warning("DEBUG: export_entries count: %d", len(export_entries))
            if export_entries:
                sample = export_entries[0]
                _LOGGER.warning("DEBUG: First export entry keys: %s", list(sample.keys()))
                _LOGGER.warning("DEBUG: Has 'rates' field: %s", "rates" in sample)
                if "rates" in sample:
                    rates_sample = sample.get("rates")
                    _LOGGER.warning("DEBUG: rates is list: %s, count: %d",
                                   isinstance(rates_sample, list),
                                   len(rates_sample) if isinstance(rates_sample, list) else 0)
                    if rates_sample:
                        _LOGGER.warning("DEBUG: First rate entry: %s", rates_sample[0])
                _LOGGER.warning("DEBUG: Sample periodFrom: %s, periodTo: %s",
                               sample.get("periodFrom"), sample.get("periodTo"))
                _LOGGER.warning("DEBUG: Sample charge type: %s", sample.get("charge", {}).get("type"))

            # Create a map of dates to data
            from datetime import datetime
            daily_map = {}

            for entry in solar_entries:
                period_from = entry.get("periodFrom", "")
                if period_from:
                    try:
                        entry_date = datetime.fromisoformat(period_from.replace("Z", "+00:00"))
                        date_key = entry_date.strftime("%Y-%m-%d")

                        if date_key not in daily_map:
                            daily_map[date_key] = {
                                "date": date_key,
                                "day_name": entry_date.strftime("%A"),
                                "day": entry_date.day,
                                "month": entry_date.month,
                                "year": entry_date.year,
                            }

                        daily_map[date_key]["solar_consumption"] = entry.get("consumption", 0)
                        daily_map[date_key]["solar_charge"] = entry.get("charge", {}).get("value", 0)
                    except Exception as err:
                        pass

            for entry in export_entries:
                period_from = entry.get("periodFrom", "")
                if period_from:
                    try:
                        entry_date = datetime.fromisoformat(period_from.replace("Z", "+00:00"))
                        date_key = entry_date.strftime("%Y-%m-%d")

                        if date_key not in daily_map:
                            daily_map[date_key] = {
                                "date": date_key,
                                "day_name": entry_date.strftime("%A"),
                                "day": entry_date.day,
                                "month": entry_date.month,
                                "year": entry_date.year,
                                "periodFrom": entry.get("periodFrom"),
                                "periodTo": entry.get("periodTo"),
                                "grid_rates_kwh": {},
                                "grid_rates_aud": {},
                            }

                        # Ensure rate dictionaries exist even if solar_entries created the date
                        if "grid_rates_kwh" not in daily_map[date_key]:
                            daily_map[date_key]["grid_rates_kwh"] = {}
                            daily_map[date_key]["grid_rates_aud"] = {}
                            daily_map[date_key]["periodFrom"] = entry.get("periodFrom")
                            daily_map[date_key]["periodTo"] = entry.get("periodTo")

                        charge_type = entry.get("charge", {}).get("type", "DEBIT")
                        consumption = entry.get("consumption", 0)
                        charge_value = entry.get("charge", {}).get("value", 0)

                        if charge_type == "CREDIT":
                            daily_map[date_key]["return_to_grid"] = consumption
                            daily_map[date_key]["return_to_grid_charge"] = charge_value
                            daily_map[date_key]["grid_consumption"] = 0
                            daily_map[date_key]["grid_charge"] = 0
                        else:
                            daily_map[date_key]["grid_consumption"] = consumption
                            daily_map[date_key]["grid_charge"] = charge_value
                            daily_map[date_key]["return_to_grid"] = 0
                            daily_map[date_key]["return_to_grid_charge"] = 0

                        # Extract rates breakdown
                        rates_list = entry.get("rates", [])
                        # DEBUG: Log per-entry rate extraction
                        _LOGGER.warning("DEBUG: date=%s, charge_type=%s, has_rates=%s, rates_count=%d",
                                       date_key, charge_type, "rates" in entry,
                                       len(rates_list) if rates_list else 0)
                        if rates_list and isinstance(rates_list, list):
                            _LOGGER.warning("DEBUG: Processing %d rate entries for %s", len(rates_list), date_key)
                            for rate_entry in rates_list:
                                if not isinstance(rate_entry, dict):
                                    continue

                                rate_type = rate_entry.get("type")
                                if not rate_type:
                                    continue

                                consumption = rate_entry.get("consumption", 0)
                                charge_obj = rate_entry.get("charge", {})
                                charge_value = abs(charge_obj.get("value", 0)) if isinstance(charge_obj, dict) else 0

                                # Accumulate by rate type
                                daily_map[date_key]["grid_rates_kwh"][rate_type] = \
                                    daily_map[date_key]["grid_rates_kwh"].get(rate_type, 0) + consumption
                                daily_map[date_key]["grid_rates_aud"][rate_type] = \
                                    daily_map[date_key]["grid_rates_aud"].get(rate_type, 0) + charge_value

                                # DEBUG: Log accumulation
                                _LOGGER.warning("DEBUG: Accumulated %s for %s: kwh=%.2f, aud=%.2f",
                                               rate_type, date_key,
                                               daily_map[date_key]["grid_rates_kwh"][rate_type],
                                               daily_map[date_key]["grid_rates_aud"][rate_type])
                    except Exception as err:
                        pass

            # Convert to sorted list (newest first)
            all_daily_entries = sorted(daily_map.values(), key=lambda x: x["date"], reverse=True)

            # Last 3 days (most recent 3) - reversed to show oldest to newest
            processed["last_3_days"] = list(reversed(all_daily_entries[:3])) if len(all_daily_entries) >= 3 else list(reversed(all_daily_entries))

            # Last 7 days totals
            last_7 = all_daily_entries[:7] if len(all_daily_entries) >= 7 else all_daily_entries
            if last_7:
                processed["last_7_days"] = {
                    "solar_consumption": sum(d.get("solar_consumption", 0) for d in last_7),
                    "solar_charge": sum(d.get("solar_charge", 0) for d in last_7),
                    "grid_consumption": sum(d.get("grid_consumption", 0) for d in last_7),
                    "grid_charge": sum(d.get("grid_charge", 0) for d in last_7),
                    "return_to_grid": sum(d.get("return_to_grid", 0) for d in last_7),
                    "return_to_grid_charge": sum(d.get("return_to_grid_charge", 0) for d in last_7),
                    "days": len(last_7),
                }

            # Month to date (current month entries)
            mtd_entries = [d for d in all_daily_entries if d["month"] == current_month and d["year"] == current_year]
            if mtd_entries:
                processed["month_to_date"] = {
                    "solar_consumption": sum(d.get("solar_consumption", 0) for d in mtd_entries),
                    "solar_charge": sum(d.get("solar_charge", 0) for d in mtd_entries),
                    "grid_consumption": sum(d.get("grid_consumption", 0) for d in mtd_entries),
                    "grid_charge": sum(d.get("grid_charge", 0) for d in mtd_entries),
                    "return_to_grid": sum(d.get("return_to_grid", 0) for d in mtd_entries),
                    "return_to_grid_charge": sum(d.get("return_to_grid_charge", 0) for d in mtd_entries),
                    "days": len(mtd_entries),
                }

            # Last month (previous month entries)
            last_month_num = current_month - 1 if current_month > 1 else 12
            last_month_year = current_year if current_month > 1 else current_year - 1
            last_month_entries = [d for d in all_daily_entries if d["month"] == last_month_num and d["year"] == last_month_year]
            if last_month_entries:
                processed["last_month"] = {
                    "solar_consumption": sum(d.get("solar_consumption", 0) for d in last_month_entries),
                    "solar_charge": sum(d.get("solar_charge", 0) for d in last_month_entries),
                    "grid_consumption": sum(d.get("grid_consumption", 0) for d in last_month_entries),
                    "grid_charge": sum(d.get("grid_charge", 0) for d in last_month_entries),
                    "return_to_grid": sum(d.get("return_to_grid", 0) for d in last_month_entries),
                    "return_to_grid_charge": sum(d.get("return_to_grid_charge", 0) for d in last_month_entries),
                    "days": len(last_month_entries),
                }

            # Monthly daily breakdown (for graphing)
            solar_daily_breakdown = []
            if "solar" in daily_data and daily_data["solar"]:
                for entry in daily_data["solar"]:
                    period_from = entry.get("periodFrom", "")
                    if period_from:
                        try:
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
                            continue

            # Process export daily breakdown
            grid_daily_breakdown = []
            return_daily_breakdown = []
            if "export" in daily_data and daily_data["export"]:
                for entry in daily_data["export"]:
                    period_from = entry.get("periodFrom", "")
                    if period_from:
                        try:
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

        # ====================
        # ADVANCED ANALYTICS (10 new features)
        # ====================

        # Feature 2: Week-over-Week Comparison
        if len(all_daily_entries) >= 14:
            this_week = all_daily_entries[:7]
            last_week = all_daily_entries[7:14]

            this_week_solar = sum(d.get("solar_consumption", 0) for d in this_week)
            last_week_solar = sum(d.get("solar_consumption", 0) for d in last_week)
            this_week_grid = sum(d.get("grid_consumption", 0) for d in this_week)
            last_week_grid = sum(d.get("grid_consumption", 0) for d in last_week)
            this_week_cost = sum(d.get("solar_charge", 0) + d.get("grid_charge", 0) for d in this_week)
            last_week_cost = sum(d.get("solar_charge", 0) + d.get("grid_charge", 0) for d in last_week)

            processed["week_comparison"] = {
                "this_week_solar": round(this_week_solar, 2),
                "last_week_solar": round(last_week_solar, 2),
                "solar_change": round(this_week_solar - last_week_solar, 2),
                "solar_change_pct": round(((this_week_solar - last_week_solar) / last_week_solar * 100) if last_week_solar > 0 else 0, 2),
                "this_week_grid": round(this_week_grid, 2),
                "last_week_grid": round(last_week_grid, 2),
                "grid_change": round(this_week_grid - last_week_grid, 2),
                "grid_change_pct": round(((this_week_grid - last_week_grid) / last_week_grid * 100) if last_week_grid > 0 else 0, 2),
                "this_week_cost": round(this_week_cost, 2),
                "last_week_cost": round(last_week_cost, 2),
                "cost_change": round(this_week_cost - last_week_cost, 2),
                "cost_change_pct": round(((this_week_cost - last_week_cost) / last_week_cost * 100) if last_week_cost > 0 else 0, 2),
            }

        # Feature 3: Weekday vs Weekend Analysis
        if all_daily_entries:
            from datetime import datetime as dt
            weekday_entries = []
            weekend_entries = []

            for entry in all_daily_entries:
                try:
                    date_str = entry.get("date", "")
                    if date_str:
                        date_obj = dt.strptime(date_str, "%Y-%m-%d")
                        # Monday = 0, Sunday = 6
                        if date_obj.weekday() < 5:  # Monday-Friday
                            weekday_entries.append(entry)
                        else:  # Saturday-Sunday
                            weekend_entries.append(entry)
                except:
                    continue

            if weekday_entries:
                weekday_count = len(weekday_entries)
                processed["weekday_analysis"] = {
                    "avg_solar": round(sum(d.get("solar_consumption", 0) for d in weekday_entries) / weekday_count, 2),
                    "avg_grid": round(sum(d.get("grid_consumption", 0) for d in weekday_entries) / weekday_count, 2),
                    "avg_cost": round(sum(d.get("solar_charge", 0) + d.get("grid_charge", 0) for d in weekday_entries) / weekday_count, 2),
                    "days": weekday_count,
                }

            if weekend_entries:
                weekend_count = len(weekend_entries)
                processed["weekend_analysis"] = {
                    "avg_solar": round(sum(d.get("solar_consumption", 0) for d in weekend_entries) / weekend_count, 2),
                    "avg_grid": round(sum(d.get("grid_consumption", 0) for d in weekend_entries) / weekend_count, 2),
                    "avg_cost": round(sum(d.get("solar_charge", 0) + d.get("grid_charge", 0) for d in weekend_entries) / weekend_count, 2),
                    "days": weekend_count,
                }

        # Feature 5: Solar Self-Sufficiency Score
        if all_daily_entries:
            # Calculate for last 7 days
            last_7_for_score = all_daily_entries[:7]
            total_solar = sum(d.get("solar_consumption", 0) for d in last_7_for_score)
            total_grid = sum(d.get("grid_consumption", 0) for d in last_7_for_score)
            total_consumption = total_solar + total_grid

            processed["self_sufficiency"] = {
                "score": round((total_solar / total_consumption * 100) if total_consumption > 0 else 0, 2),
                "solar_kwh": round(total_solar, 2),
                "grid_kwh": round(total_grid, 2),
                "total_kwh": round(total_consumption, 2),
                "period_days": len(last_7_for_score),
            }

        # Feature 6: High Usage Day Rankings (Top 5 in last 30 days)
        if all_daily_entries:
            last_30 = all_daily_entries[:30] if len(all_daily_entries) >= 30 else all_daily_entries
            # Calculate total consumption per day
            days_with_total = []
            for day in last_30:
                total_day_consumption = day.get("solar_consumption", 0) + day.get("grid_consumption", 0)
                total_day_cost = day.get("solar_charge", 0) + day.get("grid_charge", 0)
                days_with_total.append({
                    "date": day.get("date"),
                    "day_name": day.get("day_name"),
                    "total_consumption": round(total_day_consumption, 2),
                    "total_cost": round(total_day_cost, 2),
                    "solar": round(day.get("solar_consumption", 0), 2),
                    "grid": round(day.get("grid_consumption", 0), 2),
                })

            # Sort by total consumption descending
            top_5 = sorted(days_with_total, key=lambda x: x["total_consumption"], reverse=True)[:5]
            processed["high_usage_days"] = top_5

        # Feature 8: Cost Per kWh Tracking
        if all_daily_entries:
            # Last 7 days
            last_7_cost = all_daily_entries[:7]
            total_cost_7d = sum(d.get("solar_charge", 0) + d.get("grid_charge", 0) for d in last_7_cost)
            total_consumption_7d = sum(d.get("solar_consumption", 0) + d.get("grid_consumption", 0) for d in last_7_cost)

            grid_cost_7d = sum(d.get("grid_charge", 0) for d in last_7_cost)
            grid_consumption_7d = sum(d.get("grid_consumption", 0) for d in last_7_cost)

            solar_cost_7d = sum(d.get("solar_charge", 0) for d in last_7_cost)
            solar_consumption_7d = sum(d.get("solar_consumption", 0) for d in last_7_cost)

            processed["cost_per_kwh"] = {
                "overall": round(total_cost_7d / total_consumption_7d, 4) if total_consumption_7d > 0 else 0,
                "grid": round(grid_cost_7d / grid_consumption_7d, 4) if grid_consumption_7d > 0 else 0,
                "solar": round(solar_cost_7d / solar_consumption_7d, 4) if solar_consumption_7d > 0 else 0,
                "total_cost": round(total_cost_7d, 2),
                "total_consumption": round(total_consumption_7d, 2),
            }

        # Feature 9: Monthly Cost Projection
        if mtd_entries:
            mtd_days = len(mtd_entries)
            mtd_cost = sum(d.get("solar_charge", 0) + d.get("grid_charge", 0) for d in mtd_entries)

            # Get days in current month
            import calendar
            days_in_month = calendar.monthrange(current_year, current_month)[1]
            days_remaining = days_in_month - mtd_days

            daily_avg = mtd_cost / mtd_days if mtd_days > 0 else 0
            projected_total = daily_avg * days_in_month
            projected_remaining = daily_avg * days_remaining

            processed["monthly_projection"] = {
                "projected_total": round(projected_total, 2),
                "current_mtd": round(mtd_cost, 2),
                "projected_remaining": round(projected_remaining, 2),
                "daily_average": round(daily_avg, 2),
                "days_elapsed": mtd_days,
                "days_remaining": days_remaining,
                "days_in_month": days_in_month,
            }

        # Feature 10: Return-to-Grid Value Analysis
        if all_daily_entries:
            last_7_rtg = all_daily_entries[:7]
            rtg_kwh = sum(d.get("return_to_grid", 0) for d in last_7_rtg)
            rtg_credit = sum(d.get("return_to_grid_charge", 0) for d in last_7_rtg)

            # Also get grid purchase rate for comparison
            grid_kwh = sum(d.get("grid_consumption", 0) for d in last_7_rtg)
            grid_cost = sum(d.get("grid_charge", 0) for d in last_7_rtg)

            export_rate = abs(rtg_credit / rtg_kwh) if rtg_kwh > 0 else 0
            purchase_rate = grid_cost / grid_kwh if grid_kwh > 0 else 0

            processed["return_to_grid_analysis"] = {
                "export_kwh": round(rtg_kwh, 2),
                "export_credit": round(abs(rtg_credit), 2),  # Make positive for display
                "export_rate_per_kwh": round(export_rate, 4),
                "purchase_rate_per_kwh": round(purchase_rate, 4),
                "rate_difference": round(purchase_rate - export_rate, 4),
                "potential_savings": round(rtg_kwh * purchase_rate, 2),  # What you'd pay if you bought this power
                "actual_credit": round(abs(rtg_credit), 2),
                "opportunity_cost": round((rtg_kwh * purchase_rate) - abs(rtg_credit), 2),
            }

        return processed

    def _process_hourly_data(self, data: dict) -> dict:
        """Process hourly data.

        Unlike interval data, we keep ALL hourly entries for graphing.
        """
        # Safety check - if data is None, return empty structure
        if data is None:
            data = {}

        processed = {
            "solar_entries": [],
            "grid_entries": [],
            "return_to_grid_entries": [],
            "solar_total": 0,
            "grid_total": 0,
            "return_to_grid_total": 0,
        }

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

        # Aggregate hourly data by rate type
        hourly_rates_aggregation = {}
        try:
            # Process all export entries (grid consumption, not solar export/CREDIT)
            for entry in processed["grid_entries"]:
                rates_list = entry.get("rates", [])

                if not rates_list or not isinstance(rates_list, list):
                    # No rate breakdown for this hour, skip
                    continue

                for rate_entry in rates_list:
                    if not isinstance(rate_entry, dict):
                        continue

                    rate_type = rate_entry.get("type")
                    if not rate_type:
                        continue

                    # Initialize aggregation for this rate type
                    if rate_type not in hourly_rates_aggregation:
                        hourly_rates_aggregation[rate_type] = {
                            "consumption": 0,
                            "charge": 0,
                            "hours": 0
                        }

                    # Aggregate
                    consumption = rate_entry.get("consumption", 0)
                    charge_obj = rate_entry.get("charge", {})
                    charge_value = abs(charge_obj.get("value", 0)) if isinstance(charge_obj, dict) else 0

                    hourly_rates_aggregation[rate_type]["consumption"] += consumption
                    hourly_rates_aggregation[rate_type]["charge"] += charge_value
                    hourly_rates_aggregation[rate_type]["hours"] += 1

            # Round values
            for rate_type in hourly_rates_aggregation:
                hourly_rates_aggregation[rate_type]["consumption"] = round(
                    hourly_rates_aggregation[rate_type]["consumption"], 2
                )
                hourly_rates_aggregation[rate_type]["charge"] = round(
                    hourly_rates_aggregation[rate_type]["charge"], 2
                )

        except Exception as err:
            _LOGGER.error("Error aggregating hourly rates: %s", err)
            hourly_rates_aggregation = {}

        # Store hourly rate aggregation
        processed["hourly_rates_breakdown"] = hourly_rates_aggregation

        # ====================
        # HOURLY ANALYTICS
        # ====================

        # Feature 1: Peak Usage Time Blocks (4-hour windows)
        # Combine all consumption data with timestamps AND charge information
        from datetime import datetime as dt
        hourly_timeline = []

        for entry in processed["solar_entries"]:
            period_from = entry.get("periodFrom", "")
            if period_from:
                try:
                    timestamp = dt.fromisoformat(period_from.replace("Z", "+00:00"))
                    charge_info = entry.get("charge", {})
                    hourly_timeline.append({
                        "timestamp": timestamp,
                        "hour": timestamp.hour,
                        "consumption": entry.get("consumption", 0),
                        "type": "solar",
                        "charge_type": charge_info.get("type", "DEBIT"),
                        "charge_value": charge_info.get("value", 0),
                    })
                except:
                    continue

        for entry in processed["grid_entries"]:
            period_from = entry.get("periodFrom", "")
            if period_from:
                try:
                    timestamp = dt.fromisoformat(period_from.replace("Z", "+00:00"))
                    charge_info = entry.get("charge", {})
                    hourly_timeline.append({
                        "timestamp": timestamp,
                        "hour": timestamp.hour,
                        "consumption": entry.get("consumption", 0),
                        "type": "grid",
                        "charge_type": charge_info.get("type", "DEBIT"),
                        "charge_value": charge_info.get("value", 0),
                    })
                except:
                    continue

        # Sort by timestamp
        hourly_timeline.sort(key=lambda x: x["timestamp"])

        # Find peak 4-hour windows
        if len(hourly_timeline) >= 4:
            max_consumption = 0
            peak_window = None

            for i in range(len(hourly_timeline) - 3):
                window = hourly_timeline[i:i+4]
                window_consumption = sum(h["consumption"] for h in window)

                if window_consumption > max_consumption:
                    max_consumption = window_consumption
                    peak_window = {
                        "start_time": window[0]["timestamp"].strftime("%Y-%m-%d %H:%M"),
                        "end_time": window[3]["timestamp"].strftime("%Y-%m-%d %H:%M"),
                        "start_hour": window[0]["hour"],
                        "total_consumption": round(window_consumption, 2),
                        "hourly_breakdown": [
                            {
                                "hour": h["timestamp"].strftime("%H:%M"),
                                "consumption": round(h["consumption"], 2),
                                "type": h["type"],
                            } for h in window
                        ],
                    }

            processed["peak_4hour_window"] = peak_window

        # Feature 4: Time-of-Use Cost Breakdown (Plan-Aware)
        # Get plan configuration
        plan_type = self.plan_config.get("plan_type", "basic")
        peak_rate = self.plan_config.get("peak_rate", 0.35)
        shoulder_rate = self.plan_config.get("shoulder_rate", 0.25)
        off_peak_rate = self.plan_config.get("off_peak_rate", 0.18)
        ev_rate = self.plan_config.get("ev_rate", 0.06)
        flat_rate = self.plan_config.get("flat_rate", 0.28)

        tou_breakdown = {
            "peak": {"consumption": 0, "cost": 0, "hours": 0},
            "shoulder": {"consumption": 0, "cost": 0, "hours": 0},
            "off_peak": {"consumption": 0, "cost": 0, "hours": 0},
        }

        # Free usage and savings tracking (month-to-date)
        # Filter hourly_timeline to only include entries from current month
        from datetime import datetime, timezone, timedelta
        now_utc = datetime.now(timezone.utc)
        current_month = now_utc.month
        current_year = now_utc.year

        # Filter to current month entries for free usage and EV tracking
        mtd_hourly = [
            entry for entry in hourly_timeline
            if entry["timestamp"].month == current_month and entry["timestamp"].year == current_year
        ]

        # Filter to last 7 days for weekly tracking
        seven_days_ago = now_utc - timedelta(days=7)
        last_7_days_hourly = [
            entry for entry in hourly_timeline
            if entry["timestamp"] >= seven_days_ago
        ]

        # Filter to current year for yearly tracking
        ytd_hourly = [
            entry for entry in hourly_timeline
            if entry["timestamp"].year == current_year
        ]

        # Initialize tracking dictionaries
        free_usage_mtd = {"consumption": 0, "cost_saved": 0, "hours": 0}
        ev_usage_mtd = {"consumption": 0, "cost": 0, "cost_saved": 0, "hours": 0}
        ev_usage_weekly = {"consumption": 0, "cost": 0, "cost_saved": 0, "hours": 0}
        ev_usage_yearly = {"consumption": 0, "cost": 0, "cost_saved": 0, "hours": 0}

        # Calculate free usage (MTD only) and EV usage (MTD)
        # NOW USING API charge_type INSTEAD OF HARDCODED TIME WINDOWS!
        for entry in mtd_hourly:
            timestamp = entry["timestamp"]
            hour = timestamp.hour
            consumption = entry["consumption"]
            charge_type = entry.get("charge_type", "DEBIT")
            charge_value = abs(entry.get("charge_value", 0))  # Absolute value for cost

            # Track FREE periods from API (charge_type = "FREE")
            if charge_type == "FREE":
                free_usage_mtd["consumption"] += consumption
                free_usage_mtd["hours"] += 1
                # Calculate savings: what it WOULD have cost at shoulder rate
                free_usage_mtd["cost_saved"] += consumption * shoulder_rate

            # Track EV charging (00:00-06:00) for EV plan - keep time-based for now
            # TODO: Check if OVO API has special charge_type for EV periods
            if plan_type == "ev" and 0 <= hour < 6:
                ev_usage_mtd["consumption"] += consumption
                ev_usage_mtd["cost"] += charge_value  # Use actual cost from API
                ev_usage_mtd["hours"] += 1
                # Calculate savings vs off-peak rate
                ev_usage_mtd["cost_saved"] += consumption * (off_peak_rate - ev_rate)

        # Calculate EV usage for last 7 days (weekly)
        for entry in last_7_days_hourly:
            timestamp = entry["timestamp"]
            hour = timestamp.hour
            consumption = entry["consumption"]
            charge_value = abs(entry.get("charge_value", 0))

            if plan_type == "ev" and 0 <= hour < 6:
                ev_usage_weekly["consumption"] += consumption
                ev_usage_weekly["cost"] += charge_value  # Use actual cost from API
                ev_usage_weekly["hours"] += 1
                ev_usage_weekly["cost_saved"] += consumption * (off_peak_rate - ev_rate)

        # Calculate EV usage for current year (yearly)
        for entry in ytd_hourly:
            timestamp = entry["timestamp"]
            hour = timestamp.hour
            consumption = entry["consumption"]
            charge_value = abs(entry.get("charge_value", 0))

            if plan_type == "ev" and 0 <= hour < 6:
                ev_usage_yearly["consumption"] += consumption
                ev_usage_yearly["cost"] += charge_value  # Use actual cost from API
                ev_usage_yearly["hours"] += 1
                ev_usage_yearly["cost_saved"] += consumption * (off_peak_rate - ev_rate)

        # Now process TOU breakdown across all hourly data (last 7 days)
        # USE API charge_type FOR ACCURATE CLASSIFICATION!
        for entry in hourly_timeline:
            timestamp = entry["timestamp"]
            hour = timestamp.hour
            consumption = entry["consumption"]
            charge_type = entry.get("charge_type", "DEBIT")
            charge_value = abs(entry.get("charge_value", 0))

            # Map API charge_type to our TOU periods
            # API returns: PEAK, OFF_PEAK, SHOULDER, FREE, DEBIT, CREDIT
            period = None
            skip_entry = False

            if charge_type == "PEAK":
                period = "peak"
                cost = charge_value
            elif charge_type == "OFF_PEAK":
                period = "off_peak"
                cost = charge_value
            elif charge_type in ["SHOULDER", "DEBIT"]:
                # DEBIT is typically shoulder period or could be any consumption
                period = "shoulder"
                cost = charge_value
            elif charge_type == "FREE":
                # Free periods tracked separately, skip from TOU
                skip_entry = True
            elif charge_type == "CREDIT":
                # Solar export, skip from consumption TOU
                skip_entry = True

            # Add to appropriate period
            if period and not skip_entry and consumption > 0:
                tou_breakdown[period]["consumption"] += consumption
                tou_breakdown[period]["cost"] += cost
                tou_breakdown[period]["hours"] += 1

        # Round values
        for period in tou_breakdown:
            tou_breakdown[period]["consumption"] = round(tou_breakdown[period]["consumption"], 2)
            tou_breakdown[period]["cost"] = round(tou_breakdown[period]["cost"], 2)

        # Round free usage (MTD)
        free_usage_mtd["consumption"] = round(free_usage_mtd["consumption"], 2)
        free_usage_mtd["cost_saved"] = round(free_usage_mtd["cost_saved"], 2)

        # Round EV usage (all periods)
        ev_usage_mtd["consumption"] = round(ev_usage_mtd["consumption"], 2)
        ev_usage_mtd["cost"] = round(ev_usage_mtd["cost"], 2)
        ev_usage_mtd["cost_saved"] = round(ev_usage_mtd["cost_saved"], 2)

        ev_usage_weekly["consumption"] = round(ev_usage_weekly["consumption"], 2)
        ev_usage_weekly["cost"] = round(ev_usage_weekly["cost"], 2)
        ev_usage_weekly["cost_saved"] = round(ev_usage_weekly["cost_saved"], 2)

        ev_usage_yearly["consumption"] = round(ev_usage_yearly["consumption"], 2)
        ev_usage_yearly["cost"] = round(ev_usage_yearly["cost"], 2)
        ev_usage_yearly["cost_saved"] = round(ev_usage_yearly["cost_saved"], 2)

        processed["time_of_use"] = tou_breakdown
        processed["free_usage"] = free_usage_mtd
        processed["ev_usage"] = ev_usage_mtd  # Keep for backward compatibility
        processed["ev_usage_weekly"] = ev_usage_weekly
        processed["ev_usage_monthly"] = ev_usage_mtd  # Explicit monthly
        processed["ev_usage_yearly"] = ev_usage_yearly

        # Feature 7: Hourly Heatmap Data (day-of-week averages)
        heatmap_data = {}  # Structure: {day_name: {hour: {consumption, count}}}

        for entry in hourly_timeline:
            timestamp = entry["timestamp"]
            day_name = timestamp.strftime("%A")
            hour = timestamp.hour

            if day_name not in heatmap_data:
                heatmap_data[day_name] = {}

            if hour not in heatmap_data[day_name]:
                heatmap_data[day_name][hour] = {"total": 0, "count": 0}

            heatmap_data[day_name][hour]["total"] += entry["consumption"]
            heatmap_data[day_name][hour]["count"] += 1

        # Calculate averages
        heatmap_averages = {}
        for day_name, hours in heatmap_data.items():
            heatmap_averages[day_name] = {}
            for hour, data in hours.items():
                heatmap_averages[day_name][hour] = round(data["total"] / data["count"], 2) if data["count"] > 0 else 0

        processed["hourly_heatmap"] = heatmap_averages

        return processed
