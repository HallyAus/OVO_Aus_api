"""Data coordinator for OVO Energy Australia."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .analytics.hourly import process_hourly_data
from .analytics.insights import compute_insights
from .analytics.interval import process_interval_data
from .api import (
    OVOEnergyAUApiClient,
    OVOEnergyAUApiClientAuthenticationError,
    OVOEnergyAUApiClientCommunicationError,
    OVOEnergyAUApiClientError,
)
from .const import DOMAIN, FAST_UPDATE_INTERVAL
from .models import PlanConfig

_LOGGER = logging.getLogger(__name__)


class OVOEnergyAUDataUpdateCoordinator(DataUpdateCoordinator):
    """Fetch and process data from OVO Energy Australia API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: OVOEnergyAUApiClient,
        account_id: str,
        plan_config: PlanConfig | None = None,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.account_id = account_id
        self.plan_config = plan_config or PlanConfig()

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=FAST_UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from OVO Energy API."""
        try:
            # 1. Interval data (daily/monthly/yearly)
            interval_data = await self.client.get_interval_data(self.account_id)
            processed = process_interval_data(interval_data)

            # 2. Product agreements (plan info)
            try:
                processed["product_agreements"] = await self.client.get_product_agreements(
                    self.account_id
                )
            except Exception as err:
                _LOGGER.error("Failed to fetch product agreements: %s", err)
                processed["product_agreements"] = None

            # 3. Hourly data - fetch last 8 days to cover all 7-day-ago sensors
            # and handle month boundaries (e.g., yesterday on the 1st)
            now = dt_util.now()
            from datetime import timedelta
            query_start = (now - timedelta(days=8)).strftime("%Y-%m-%d")
            query_end = now.strftime("%Y-%m-%d")

            try:
                hourly_raw = await self.client.get_hourly_data(
                    self.account_id, query_start, query_end
                )
                processed["hourly"] = process_hourly_data(
                    hourly_raw or {}, self.plan_config
                )
            except Exception as err:
                _LOGGER.warning("Failed to fetch hourly data: %s", err)
                processed["hourly"] = process_hourly_data({}, self.plan_config)

            # 4. Analytics insights
            compute_insights(processed)

            return processed

        except OVOEnergyAUApiClientAuthenticationError as err:
            raise ConfigEntryAuthFailed(err) from err
        except OVOEnergyAUApiClientCommunicationError as err:
            raise UpdateFailed(f"Communication error: {err}") from err
        except OVOEnergyAUApiClientError as err:
            raise UpdateFailed(f"API error: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching OVO Energy data")
            raise UpdateFailed(f"Error fetching data: {err}") from err

    @staticmethod
    def analyze_plan_and_rates(hourly_data: dict) -> dict:
        """Analyze hourly data to detect plan type and actual rates.

        Returns dict with plan_type, confidence, rates, charge_types_found.
        """
        result = {
            "plan_type": "basic",
            "confidence": 0,
            "rates": {"peak": 0.35, "shoulder": 0.25, "off_peak": 0.18, "ev": 0.06},
            "charge_types_found": [],
        }

        if not hourly_data:
            return result

        charge_types = set()
        rate_samples = {"peak": [], "shoulder": [], "off_peak": [], "free": []}

        for source in ["export"]:
            for entry in hourly_data.get(source, []) or []:
                charge = entry.get("charge", {})
                charge_type = charge.get("type", "")
                charge_value = abs(charge.get("value", 0))
                consumption = entry.get("consumption", 0)

                if charge_type:
                    charge_types.add(charge_type)

                if consumption > 0 and charge_value > 0:
                    rate = charge_value / consumption
                    if charge_type == "PEAK":
                        rate_samples["peak"].append(rate)
                    elif charge_type == "OFF_PEAK":
                        rate_samples["off_peak"].append(rate)
                    elif charge_type in ["SHOULDER", "DEBIT"]:
                        rate_samples["shoulder"].append(rate)

        result["charge_types_found"] = list(charge_types)

        for period, samples in rate_samples.items():
            if samples and period != "free":
                result["rates"][period] = round(sum(samples) / len(samples), 4)

        has_free = "FREE" in charge_types
        has_peak = "PEAK" in charge_types
        has_off_peak = "OFF_PEAK" in charge_types

        if has_free and has_peak and has_off_peak:
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
            result["plan_type"] = "free_3"
            result["confidence"] = 75
        elif has_peak and has_off_peak:
            result["plan_type"] = "basic"
            result["confidence"] = 90
        elif len(charge_types) <= 2 and "DEBIT" in charge_types:
            result["plan_type"] = "one"
            result["confidence"] = 60
            if rate_samples["shoulder"]:
                result["rates"]["flat"] = round(
                    sum(rate_samples["shoulder"]) / len(rate_samples["shoulder"]), 4
                )
        else:
            result["plan_type"] = "basic"
            result["confidence"] = 30

        return result
