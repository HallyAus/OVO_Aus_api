"""Data coordinator for OVO Energy Australia."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .analytics.billing import current_cycle_bounds
from .analytics.hourly import process_hourly_data
from .analytics.insights import compute_insights
from .analytics.interval import process_interval_data
from .api import (
    OVOEnergyAUApiClient,
    OVOEnergyAUApiClientAuthenticationError,
    OVOEnergyAUApiClientCommunicationError,
    OVOEnergyAUApiClientError,
)
from .const import AU_TIMEZONE, DOMAIN, FAST_UPDATE_INTERVAL
from .models import PlanConfig

_LOGGER = logging.getLogger(__name__)


class OVOEnergyAUDataUpdateCoordinator(TimestampDataUpdateCoordinator):
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
        self._vehicle_warning_active = False

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
            processed = process_interval_data(
                interval_data, self.plan_config.billing_cycle_day
            )

            # 2. Product agreements (plan info)
            try:
                processed["product_agreements"] = await self.client.get_product_agreements(
                    self.account_id
                )
            except OVOEnergyAUApiClientAuthenticationError:
                raise
            except Exception as err:
                _LOGGER.error("Failed to fetch product agreements: %s", err)
                processed["product_agreements"] = None

            # 3. Hourly data - fetch last 8 days to cover all 7-day-ago sensors
            # and handle month boundaries (e.g., yesterday on the 1st).
            # Sydney time, not HA-local: near midnight an HA instance in
            # another timezone would otherwise request the wrong date window
            now = dt_util.now(AU_TIMEZONE)
            query_start = (now - timedelta(days=8)).strftime("%Y-%m-%d")
            query_end = now.strftime("%Y-%m-%d")
            window_start = (now - timedelta(days=7)).date()
            window_end = now.date()

            try:
                hourly_raw = await self.client.get_hourly_data(
                    self.account_id, query_start, query_end
                )
                processed["hourly"] = process_hourly_data(
                    hourly_raw or {},
                    self.plan_config,
                    start_date=window_start,
                    end_date=window_end,
                )
            except OVOEnergyAUApiClientAuthenticationError:
                raise
            except Exception as err:
                _LOGGER.warning("Failed to fetch hourly data: %s", err)
                processed["hourly"] = process_hourly_data(
                    {},
                    self.plan_config,
                    start_date=window_start,
                    end_date=window_end,
                )

            # 4. Analytics insights
            compute_insights(processed, self.plan_config.billing_cycle_day)

            # 4b. Calculate bill estimate
            try:
                # Get standing charge from product agreements
                standing_daily = 0
                if processed.get("product_agreements"):
                    agreements = processed["product_agreements"].get("productAgreements", [])
                    if agreements:
                        standing_cents = agreements[0].get("product", {}).get("standingChargeCentsPerDay", 0) or 0
                        standing_daily = standing_cents / 100  # Convert to AUD

                # Month-to-date bill
                mtd = processed.get("month_to_date", {})
                mtd_days = mtd.get("days", 0) or 0
                mtd_grid = mtd.get("grid_charge", 0) or 0
                # Export credits reduce the bill. Solar generation is a
                # separate measurement and is not itself a bill credit.
                mtd_export_credit = abs(mtd.get("return_to_grid_charge", 0) or 0)
                mtd_standing = standing_daily * mtd_days
                mtd_bill = mtd_grid + mtd_standing - mtd_export_credit

                # Project the full billing cycle (calendar month when the
                # billing cycle day is 1)
                if mtd_days > 0:
                    now_au = dt_util.now(AU_TIMEZONE)
                    cycle_start, cycle_next = current_cycle_bounds(
                        now_au.date(), self.plan_config.billing_cycle_day
                    )
                    days_in_month = (cycle_next - cycle_start).days
                    daily_avg_net = mtd_bill / mtd_days
                    projected_bill = daily_avg_net * days_in_month
                    remaining_bill = daily_avg_net * (days_in_month - mtd_days)

                    processed["bill_estimate"] = {
                        "mtd_bill": round(mtd_bill, 2),
                        "mtd_grid_cost": round(mtd_grid, 2),
                        "mtd_export_credit": round(mtd_export_credit, 2),
                        "mtd_standing_charge": round(mtd_standing, 2),
                        "mtd_days": mtd_days,
                        "standing_charge_daily": round(standing_daily, 2),
                        "projected_bill": round(projected_bill, 2),
                        "remaining_estimate": round(remaining_bill, 2),
                        "daily_average_net": round(daily_avg_net, 2),
                        "days_in_month": days_in_month,
                        "days_remaining": days_in_month - mtd_days,
                    }
                else:
                    processed["bill_estimate"] = {}
            except Exception as err:
                _LOGGER.debug("Failed to calculate bill estimate: %s", err)
                processed["bill_estimate"] = {}

            # 4c. Billing statements (real bills with PDF links)
            try:
                stmt_result = await self.client.get_statements(self.account_id)
                statements = (stmt_result or {}).get("statements") or []
                # Newest first (by issue date, falling back to period end)
                statements = sorted(
                    statements,
                    key=lambda s: s.get("issueDate") or s.get("periodTo") or "",
                    reverse=True,
                )
                processed["statements"] = statements
                if statements:
                    latest = statements[0]
                    charges_total = ((latest.get("charges") or {}).get("total") or {})
                    processed["latest_bill"] = {
                        "total": charges_total.get("value"),
                        "closing_balance": (latest.get("closingBalance") or {}).get("value"),
                        "opening_balance": (latest.get("openingBalance") or {}).get("value"),
                        "period_from": latest.get("periodFrom"),
                        "period_to": latest.get("periodTo"),
                        "issue_date": latest.get("issueDate"),
                        "download_url": latest.get("downloadUrl"),
                    }
                else:
                    processed["latest_bill"] = {}
            except OVOEnergyAUApiClientAuthenticationError:
                raise
            except Exception as err:
                _LOGGER.debug("Failed to fetch statements: %s", err)
                processed["statements"] = []
                processed["latest_bill"] = {}

            # 4d. Payments + refer-a-friend
            try:
                extras = await self.client.get_account_extras(self.account_id)
                payments = sorted(
                    (extras or {}).get("payments") or [],
                    key=lambda p: p.get("date") or "",
                    reverse=True,
                )
                processed["payments"] = payments
                processed["latest_payment"] = (
                    {"amount": payments[0].get("amount"),
                     "date": payments[0].get("date"),
                     "type": payments[0].get("type")}
                    if payments else {}
                )
                raf = (extras or {}).get("raf") or {}
                processed["referral"] = {
                    "code": raf.get("referralCode"),
                    "total_earned": raf.get("totalEarned"),
                    "referral_count": len(raf.get("referrals") or []),
                }
                processed["flex"] = {
                    "onboarded": ((extras or {}).get("flex") or {}).get("hasOnboarded"),
                }
            except OVOEnergyAUApiClientAuthenticationError:
                raise
            except Exception as err:
                _LOGGER.debug("Failed to fetch account extras: %s", err)
                processed["payments"] = []
                processed["latest_payment"] = {}
                processed["referral"] = {}
                processed["flex"] = {}

            # 4e. Account metadata is also the source of the customer ID used
            # for OVO's separate, account-scoped Kaluza vehicle sign-in.
            customer_id = None
            try:
                contact_info = await self.client.get_contact_info()
                accounts = contact_info.get("accounts", [])
                active = [a for a in accounts if not a.get("closed", False)]
                # Match this entry's account — a multi-account customer must
                # not see another account's balance or vehicle data.
                account = next(
                    (a for a in active if str(a.get("id")) == str(self.account_id)),
                    active[0] if active else None,
                )
                if account:
                    processed["account_balance"] = account.get(
                        "customerOrientatedBalance"
                    )
                    processed["has_solar"] = account.get("hasSolar", False)
                    customer_id = account.get("customerId")
            except OVOEnergyAUApiClientAuthenticationError:
                raise
            except Exception as err:
                _LOGGER.debug("Failed to fetch contact info: %s", err)
                processed["account_balance"] = None
                processed["has_solar"] = None

            # 4f. Read-only Kaluza vehicle telemetry, preferences, schedules,
            # charge plan, and monthly device energy. `flex.hasOnboarded` is a
            # separate MyOVO feature flag and is not a reliable EV Control
            # indicator, so vehicle discovery must be probed independently.
            try:
                processed["vehicles"] = await self.client.get_vehicle_data(
                    self.account_id, customer_id
                )
                processed["vehicle_status"] = (
                    "available" if processed["vehicles"] else "none_found"
                )
                if self._vehicle_warning_active:
                    _LOGGER.info("Vehicle data access has recovered")
                    self._vehicle_warning_active = False
            except OVOEnergyAUApiClientAuthenticationError:
                raise
            except Exception as err:
                if not self._vehicle_warning_active:
                    _LOGGER.warning("Vehicle data is unavailable: %s", err)
                    self._vehicle_warning_active = True
                else:
                    _LOGGER.debug("Vehicle data remains unavailable: %s", err)
                processed["vehicles"] = []
                processed["vehicle_status"] = "unavailable"

            # 4g. Direct debit + current unbilled charge summary
            try:
                billing = await self.client.get_billing_overview(self.account_id)
                processed["billing_information"] = (
                    (billing or {}).get("billingInformation") or {}
                )
                processed["unbilled_charges"] = (
                    (billing or {}).get("unbilledCharges") or {}
                )
            except OVOEnergyAUApiClientAuthenticationError:
                raise
            except Exception as err:
                _LOGGER.debug("Failed to fetch billing overview: %s", err)
                processed["billing_information"] = {}
                processed["unbilled_charges"] = {}

            # 5. Usage info (timezone, meter type)
            try:
                usage_info = await self.client.get_usage_info(self.account_id)
                usage_v2 = (usage_info or {}).get("usageV2") or {}
                processed["meter_type"] = usage_v2.get("meterType")
                processed["api_timezone"] = usage_v2.get("timezone")
                last_read = (usage_v2.get("lastMeterRead") or {}).get("date")
                processed["last_meter_read"] = last_read
            except OVOEnergyAUApiClientAuthenticationError:
                raise
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
