"""Data coordinator for OVO Energy Australia."""

from __future__ import annotations

import logging
from datetime import timedelta

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

            # 5. Account balance from contact info
            try:
                contact_info = await self.client.get_contact_info()
                accounts = contact_info.get("accounts", [])
                active = [a for a in accounts if not a.get("closed", False)]
                if active:
                    processed["account_balance"] = active[0].get("customerOrientatedBalance")
                    processed["has_solar"] = active[0].get("hasSolar", False)
            except Exception as err:
                _LOGGER.debug("Failed to fetch contact info: %s", err)
                processed["account_balance"] = None
                processed["has_solar"] = None

            # 6. Usage info (timezone, meter type)
            try:
                usage_info = await self.client.get_usage_info(self.account_id)
                usage_v2 = (usage_info or {}).get("usageV2") or {}
                processed["meter_type"] = usage_v2.get("meterType")
                processed["api_timezone"] = usage_v2.get("timezone")
                last_read = (usage_v2.get("lastMeterRead") or {}).get("date")
                processed["last_meter_read"] = last_read
            except Exception as err:
                _LOGGER.debug("Failed to fetch usage info: %s", err)

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

