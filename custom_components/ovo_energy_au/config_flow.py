"""Config flow for OVO Energy Australia integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_ACCOUNT_ID,
    CONF_PLAN_TYPE,
    CONF_PEAK_RATE,
    CONF_SHOULDER_RATE,
    CONF_OFF_PEAK_RATE,
    CONF_EV_RATE,
    CONF_FLAT_RATE,
    PLAN_FREE_3,
    PLAN_EV,
    PLAN_BASIC,
    PLAN_ONE,
    PLAN_NAMES,
    DEFAULT_RATES,
)
from .api import (
    OVOEnergyAUApiClient,
    OVOEnergyAUApiClientAuthenticationError,
    OVOEnergyAUApiClientCommunicationError,
)

# Import for plan detection
import sys
from datetime import datetime, timedelta

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, username: str, password: str) -> dict[str, Any]:
    """Validate the user input by authenticating and fetching account info.

    Returns:
        dict with title, account_id
    """
    _LOGGER.info("Authenticating with OVO Energy using username/password")

    # Create async client
    session = async_get_clientsession(hass)
    client = OVOEnergyAUApiClient(session, username=username, password=password)

    try:
        # Authenticate and get tokens
        await client.authenticate_with_password(username, password)

        # Get account ID automatically
        account_id = await client.get_account_id()
        if not account_id:
            raise InvalidAuth("Could not retrieve account ID after authentication")

        _LOGGER.info("Successfully authenticated. Account ID: %s", account_id)

        return {
            "title": f"OVO Energy AU ({account_id})",
            "account_id": account_id,
        }

    except OVOEnergyAUApiClientAuthenticationError as err:
        _LOGGER.error("Failed to authenticate with OVO Energy API: %s", err)
        raise InvalidAuth from err
    except OVOEnergyAUApiClientCommunicationError as err:
        _LOGGER.error("Communication error with OVO Energy API: %s", err)
        raise CannotConnect from err
    except Exception as err:
        _LOGGER.exception("Unexpected exception during validation")
        raise CannotConnect from err


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OVO Energy Australia."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._auth_data = {}
        self._detected_plan = None
        self._detected_rates = None

    async def _detect_plan_from_api(self, username: str, password: str, account_id: str) -> None:
        """Fetch product agreements and detect plan/rates from API."""
        try:
            # Create client and authenticate
            session = async_get_clientsession(self.hass)
            client = OVOEnergyAUApiClient(session, username=username, password=password)
            await client.authenticate_with_password(username, password)

            # Fetch product agreements (plan information)
            account_info = await client.get_product_agreements(account_id)

            # Extract product agreements
            product_agreements = account_info.get("productAgreements", [])
            if not product_agreements:
                _LOGGER.warning("No product agreements found for account %s", account_id)
                return

            # Use the first active product agreement
            agreement = product_agreements[0]
            product = agreement.get("product", {})

            # Extract plan name and rates
            plan_name = product.get("displayName", "")
            unit_rates = product.get("unitRatesCentsPerKWH", {})
            standing_charge = product.get("standingChargeCentsPerDay", 0)

            _LOGGER.info(
                "Found plan: %s, standing charge: %.2f cents/day",
                plan_name,
                standing_charge
            )

            # Map API plan name to our internal plan type
            plan_type = PLAN_BASIC  # Default fallback
            if "EV" in plan_name.upper():
                plan_type = PLAN_EV
            elif "FREE 3" in plan_name.upper() or "FREE3" in plan_name.upper():
                plan_type = PLAN_FREE_3
            elif "ONE" in plan_name.upper():
                plan_type = PLAN_ONE

            # Convert cents/kWh to $/kWh (divide by 100)
            detected_rates = {}
            if unit_rates.get("peak") is not None:
                detected_rates["peak"] = unit_rates["peak"] / 100
            if unit_rates.get("shoulder") is not None:
                detected_rates["shoulder"] = unit_rates["shoulder"] / 100
            if unit_rates.get("offPeak") is not None:
                detected_rates["off_peak"] = unit_rates["offPeak"] / 100
            if unit_rates.get("evOffPeak") is not None:
                detected_rates["ev"] = unit_rates["evOffPeak"] / 100
            if unit_rates.get("superOffPeak") is not None and unit_rates["superOffPeak"] > 0:
                # Super off-peak is the free period on some plans
                detected_rates["free"] = unit_rates["superOffPeak"] / 100
            if unit_rates.get("standard") is not None:
                detected_rates["flat"] = unit_rates["standard"] / 100
            if unit_rates.get("feedInTariff") is not None:
                detected_rates["feed_in"] = unit_rates["feedInTariff"] / 100

            self._detected_plan = plan_type
            self._detected_rates = detected_rates

            _LOGGER.info(
                "Auto-detected plan: %s (%s), rates: %s",
                PLAN_NAMES.get(plan_type, plan_type),
                plan_name,
                detected_rates
            )

        except Exception as err:
            _LOGGER.error("Failed to detect plan from API: %s", err)
            # Detection failure is not fatal, continue with defaults

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle username/password authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(
                    self.hass,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD]
                )

                # Store authentication data for later
                self._auth_data = {
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_ACCOUNT_ID: info["account_id"],
                    "title": info["title"],
                }

                # Create unique ID based on account ID
                await self.async_set_unique_id(info["account_id"])
                self._abort_if_unique_id_configured()

                # Try to detect plan and rates from API data
                try:
                    await self._detect_plan_from_api(
                        user_input[CONF_USERNAME],
                        user_input[CONF_PASSWORD],
                        info["account_id"]
                    )
                except Exception as err:
                    _LOGGER.warning("Could not auto-detect plan: %s", err)
                    # Continue anyway with defaults

                # Proceed to plan selection step
                return await self.async_step_plan()

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders={
                "info": """Enter your OVO Energy Australia account credentials.

**What we do with your credentials:**
• Stored securely in Home Assistant's encrypted storage
• Used to authenticate with OVO Energy's API every 5 minutes
• Never shared with third parties
• Account ID is automatically retrieved after login

**Why we need your password:**
• OVO's API tokens expire quickly (5 minutes)
• We re-authenticate using your credentials before each data fetch
• This ensures your sensors stay online 24/7

Your credentials are only used to access your OVO Energy data through their official API."""
            }
        )

    async def async_step_plan(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle plan selection and rate configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Merge authentication data with plan configuration
            data = {**self._auth_data}
            data[CONF_PLAN_TYPE] = user_input[CONF_PLAN_TYPE]

            # Add rate configuration based on plan type
            plan_type = user_input[CONF_PLAN_TYPE]
            default_rates = DEFAULT_RATES.get(plan_type, {})

            if plan_type == PLAN_FREE_3:
                data[CONF_PEAK_RATE] = user_input.get(CONF_PEAK_RATE, default_rates.get("peak", 0.35))
                data[CONF_SHOULDER_RATE] = user_input.get(CONF_SHOULDER_RATE, default_rates.get("shoulder", 0.25))
                data[CONF_OFF_PEAK_RATE] = user_input.get(CONF_OFF_PEAK_RATE, default_rates.get("off_peak", 0.18))
            elif plan_type == PLAN_EV:
                data[CONF_PEAK_RATE] = user_input.get(CONF_PEAK_RATE, default_rates.get("peak", 0.35))
                data[CONF_SHOULDER_RATE] = user_input.get(CONF_SHOULDER_RATE, default_rates.get("shoulder", 0.25))
                data[CONF_OFF_PEAK_RATE] = user_input.get(CONF_OFF_PEAK_RATE, default_rates.get("off_peak", 0.18))
                data[CONF_EV_RATE] = user_input.get(CONF_EV_RATE, default_rates.get("ev", 0.06))
            elif plan_type == PLAN_BASIC:
                data[CONF_PEAK_RATE] = user_input.get(CONF_PEAK_RATE, default_rates.get("peak", 0.35))
                data[CONF_SHOULDER_RATE] = user_input.get(CONF_SHOULDER_RATE, default_rates.get("shoulder", 0.25))
                data[CONF_OFF_PEAK_RATE] = user_input.get(CONF_OFF_PEAK_RATE, default_rates.get("off_peak", 0.18))
            elif plan_type == PLAN_ONE:
                data[CONF_FLAT_RATE] = user_input.get(CONF_FLAT_RATE, default_rates.get("flat", 0.28))

            return self.async_create_entry(title=self._auth_data["title"], data=data)

        # Use detected plan and rates as defaults if available
        default_plan = self._detected_plan if self._detected_plan else PLAN_BASIC
        default_rates = self._detected_rates if self._detected_rates else {}

        # Build schema with smart defaults
        plan_schema = vol.Schema({
            vol.Required(CONF_PLAN_TYPE, default=default_plan): vol.In({
                PLAN_FREE_3: PLAN_NAMES[PLAN_FREE_3],
                PLAN_EV: PLAN_NAMES[PLAN_EV],
                PLAN_BASIC: PLAN_NAMES[PLAN_BASIC],
                PLAN_ONE: PLAN_NAMES[PLAN_ONE],
            }),
            vol.Optional(CONF_PEAK_RATE, default=default_rates.get("peak", 0.35)): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_SHOULDER_RATE, default=default_rates.get("shoulder", 0.25)): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_OFF_PEAK_RATE, default=default_rates.get("off_peak", 0.18)): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_EV_RATE, default=default_rates.get("ev", 0.06)): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_FLAT_RATE, default=default_rates.get("flat", 0.28)): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
        })

        # Build description with detection info if available
        detection_info = ""
        if self._detected_plan:
            detection_info = f"\n\n✨ **Auto-Detected:** {PLAN_NAMES.get(self._detected_plan, self._detected_plan)}\n💡 Rates below are from your actual usage data!\n"

        return self.async_show_form(
            step_id="plan",
            data_schema=plan_schema,
            errors=errors,
            description_placeholders={
                "info": f"""Select your OVO Energy plan and customize rates (AUD per kWh).{detection_info}

**The Free 3 Plan:**
• Free electricity from 11:00-14:00 daily (0 c/kWh)
• Standard TOU rates outside free hours
• We'll track your free usage and calculate savings!

**The EV Plan:**
• Super off-peak EV charging 00:00-06:00 (~6 c/kWh)
• May include free period 11:00-14:00
• Standard TOU rates for other times

**The Basic Plan:**
• Standard Time-of-Use pricing
• Peak: ~15:00-21:00 weekdays
• Shoulder: Morning and evening periods
• Off-Peak: Overnight and early morning

**The One Plan:**
• Flat rate all day (no TOU periods)
• Single rate for all consumption

**Note:** Rates are customizable. Default values shown are your actual rates or typical NSW/QLD rates."""
            }
        )


    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for OVO Energy Australia."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # Update config entry with new plan settings
            data = dict(self.config_entry.data)
            data[CONF_PLAN_TYPE] = user_input[CONF_PLAN_TYPE]

            # Update rates based on plan type
            plan_type = user_input[CONF_PLAN_TYPE]
            default_rates = DEFAULT_RATES.get(plan_type, {})

            if plan_type == PLAN_FREE_3:
                data[CONF_PEAK_RATE] = user_input.get(CONF_PEAK_RATE, default_rates.get("peak", 0.35))
                data[CONF_SHOULDER_RATE] = user_input.get(CONF_SHOULDER_RATE, default_rates.get("shoulder", 0.25))
                data[CONF_OFF_PEAK_RATE] = user_input.get(CONF_OFF_PEAK_RATE, default_rates.get("off_peak", 0.18))
                # Remove unused rates
                data.pop(CONF_EV_RATE, None)
                data.pop(CONF_FLAT_RATE, None)
            elif plan_type == PLAN_EV:
                data[CONF_PEAK_RATE] = user_input.get(CONF_PEAK_RATE, default_rates.get("peak", 0.35))
                data[CONF_SHOULDER_RATE] = user_input.get(CONF_SHOULDER_RATE, default_rates.get("shoulder", 0.25))
                data[CONF_OFF_PEAK_RATE] = user_input.get(CONF_OFF_PEAK_RATE, default_rates.get("off_peak", 0.18))
                data[CONF_EV_RATE] = user_input.get(CONF_EV_RATE, default_rates.get("ev", 0.06))
                data.pop(CONF_FLAT_RATE, None)
            elif plan_type == PLAN_BASIC:
                data[CONF_PEAK_RATE] = user_input.get(CONF_PEAK_RATE, default_rates.get("peak", 0.35))
                data[CONF_SHOULDER_RATE] = user_input.get(CONF_SHOULDER_RATE, default_rates.get("shoulder", 0.25))
                data[CONF_OFF_PEAK_RATE] = user_input.get(CONF_OFF_PEAK_RATE, default_rates.get("off_peak", 0.18))
                data.pop(CONF_EV_RATE, None)
                data.pop(CONF_FLAT_RATE, None)
            elif plan_type == PLAN_ONE:
                data[CONF_FLAT_RATE] = user_input.get(CONF_FLAT_RATE, default_rates.get("flat", 0.28))
                # Remove TOU rates
                data.pop(CONF_PEAK_RATE, None)
                data.pop(CONF_SHOULDER_RATE, None)
                data.pop(CONF_OFF_PEAK_RATE, None)
                data.pop(CONF_EV_RATE, None)

            # Update the config entry
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)

            # Reload the integration to apply changes
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data={})

        # Get current plan settings or use defaults
        current_plan = self.config_entry.data.get(CONF_PLAN_TYPE, PLAN_BASIC)
        current_peak = self.config_entry.data.get(CONF_PEAK_RATE, 0.35)
        current_shoulder = self.config_entry.data.get(CONF_SHOULDER_RATE, 0.25)
        current_off_peak = self.config_entry.data.get(CONF_OFF_PEAK_RATE, 0.18)
        current_ev = self.config_entry.data.get(CONF_EV_RATE, 0.06)
        current_flat = self.config_entry.data.get(CONF_FLAT_RATE, 0.28)

        # Build options schema
        options_schema = vol.Schema({
            vol.Required(CONF_PLAN_TYPE, default=current_plan): vol.In({
                PLAN_FREE_3: PLAN_NAMES[PLAN_FREE_3],
                PLAN_EV: PLAN_NAMES[PLAN_EV],
                PLAN_BASIC: PLAN_NAMES[PLAN_BASIC],
                PLAN_ONE: PLAN_NAMES[PLAN_ONE],
            }),
            vol.Optional(CONF_PEAK_RATE, default=current_peak): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_SHOULDER_RATE, default=current_shoulder): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_OFF_PEAK_RATE, default=current_off_peak): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_EV_RATE, default=current_ev): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_FLAT_RATE, default=current_flat): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
