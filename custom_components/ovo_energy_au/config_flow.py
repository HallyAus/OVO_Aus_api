"""Config flow for OVO Energy Australia integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
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

        # Build schema based on default rates
        plan_schema = vol.Schema({
            vol.Required(CONF_PLAN_TYPE, default=PLAN_BASIC): vol.In({
                PLAN_FREE_3: PLAN_NAMES[PLAN_FREE_3],
                PLAN_EV: PLAN_NAMES[PLAN_EV],
                PLAN_BASIC: PLAN_NAMES[PLAN_BASIC],
                PLAN_ONE: PLAN_NAMES[PLAN_ONE],
            }),
            vol.Optional(CONF_PEAK_RATE, default=0.35): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_SHOULDER_RATE, default=0.25): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_OFF_PEAK_RATE, default=0.18): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_EV_RATE, default=0.06): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_FLAT_RATE, default=0.28): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
        })

        return self.async_show_form(
            step_id="plan",
            data_schema=plan_schema,
            errors=errors,
            description_placeholders={
                "info": """Select your OVO Energy plan and customize rates (AUD per kWh).

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

**Note:** Rates are customizable. Default values shown are typical NSW/QLD rates."""
            }
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
