"""Config flow for OVO Energy Australia integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    OVOEnergyAUApiClient,
    OVOEnergyAUApiClientAuthenticationError,
    OVOEnergyAUApiClientCommunicationError,
)
from .const import (
    CONF_ACCOUNT_ID,
    CONF_BILLING_CYCLE_DAY,
    CONF_EV_RATE,
    CONF_FLAT_RATE,
    CONF_OFF_PEAK_RATE,
    CONF_PEAK_END_HOUR,
    CONF_PEAK_RATE,
    CONF_PEAK_START_HOUR,
    CONF_PLAN_TYPE,
    CONF_SHOULDER_RATE,
    DEFAULT_RATES,
    DOMAIN,
    PLAN_BASIC,
    PLAN_EV,
    PLAN_FREE_3,
    PLAN_FREE_4,
    PLAN_NAMES,
    PLAN_ONE,
)
from .tariffs import detect_plan_type, get_current_agreement

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

# URLs rendered into the config-flow description. Passed via
# description_placeholders so translation strings stay URL-free
# (hassfest rule: no raw URLs in translatable content).
_DESCRIPTION_PLACEHOLDERS = {
    "ovo_url": "https://www.ovoenergy.com.au/refer/daniel16485",
    "ovo_friendly_url": "https://ovoreferralcode.com/",
    "starlink_url": "https://starlink.com/residential?referral=RC-2455784-77014-69&app_source=share",
    "github_url": "https://github.com/HallyAus/OVO_Aus_api",
}


async def validate_input(hass: HomeAssistant, username: str, password: str) -> dict[str, Any]:
    """Validate the user input by authenticating and fetching account info.

    Returns:
        dict with title, account_id, client (authenticated client to reuse)
    """
    _LOGGER.debug("Authenticating with OVO Energy using username/password")

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

        _LOGGER.debug("Successfully authenticated")

        return {
            "title": f"OVO Energy AU ({account_id})",
            "account_id": account_id,
            "client": client,  # Return authenticated client to reuse
        }

    except InvalidAuth:
        # Raised above when no account ID comes back — don't let the generic
        # handler below re-label it as a connection problem
        raise
    except OVOEnergyAUApiClientAuthenticationError as err:
        _LOGGER.error("Failed to authenticate with OVO Energy API: %s", type(err).__name__)
        raise InvalidAuth from None
    except OVOEnergyAUApiClientCommunicationError as err:
        _LOGGER.error("Communication error with OVO Energy API: %s", type(err).__name__)
        raise CannotConnect from None
    except Exception as err:
        _LOGGER.error("Unexpected validation failure (%s)", type(err).__name__)
        raise CannotConnect from None


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OVO Energy Australia."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._auth_data = {}
        self._detected_plan = None
        self._detected_rates = None
        self._reauth_entry = None

    async def _detect_plan_from_api(self, client: OVOEnergyAUApiClient, account_id: str) -> None:
        """Fetch product agreements and detect plan/rates from API.

        Args:
            client: Already authenticated API client (reuse to avoid double auth)
            account_id: The account ID to fetch plan info for
        """
        try:
            # Fetch product agreements (plan information)
            # Client is already authenticated, no need to auth again
            account_info = await client.get_product_agreements(account_id)

            # Extract product agreements
            product_agreements = account_info.get("productAgreements", [])
            if not product_agreements:
                _LOGGER.warning("No product agreements found")
                return

            # Prefer the active/latest agreement. OVO can retain the completed
            # product before the current one after a plan switch.
            agreement = get_current_agreement(account_info)
            product = agreement.get("product", {})

            # Extract plan name and rates
            plan_name = product.get("displayName", "")
            unit_rates = product.get("unitRatesCentsPerKWH", {})
            standing_charge = product.get("standingChargeCentsPerDay", 0)

            _LOGGER.debug(
                "Found plan: %s, standing charge: %.2f cents/day",
                plan_name,
                standing_charge
            )

            # Map every known current/legacy product name, including Basic
            # variants such as "The Basic Free 4 Plan".
            plan_type = detect_plan_type(plan_name) or PLAN_BASIC

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
            if unit_rates.get("standard") is not None:
                detected_rates["flat"] = unit_rates["standard"] / 100
            if unit_rates.get("feedInTariff") is not None:
                detected_rates["feed_in"] = unit_rates["feedInTariff"] / 100

            self._detected_plan = plan_type
            self._detected_rates = detected_rates

            _LOGGER.debug(
                "Auto-detected plan: %s (%s), rates: %s",
                PLAN_NAMES.get(plan_type, plan_type),
                plan_name,
                detected_rates
            )

        except Exception as err:
            _LOGGER.error("Failed to detect plan from API: %s", type(err).__name__)
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

                # Auto-detect plan and rates from API data
                # Reuse the already-authenticated client to avoid double authentication
                try:
                    await self._detect_plan_from_api(
                        info["client"],  # Reuse authenticated client
                        info["account_id"]
                    )
                except Exception as err:
                    _LOGGER.warning("Could not auto-detect plan: %s. Using defaults.", type(err).__name__)
                    # Set defaults if detection fails
                    self._detected_plan = PLAN_BASIC
                    self._detected_rates = {}

                # Create entry with auto-detected plan data (no manual selection)
                data = {**self._auth_data}
                data[CONF_PLAN_TYPE] = self._detected_plan or PLAN_BASIC

                # Use detected rates or plan-specific defaults
                detected_rates = self._detected_rates or {}
                default_rates = DEFAULT_RATES.get(data[CONF_PLAN_TYPE], {})
                data[CONF_PEAK_RATE] = detected_rates.get(
                    "peak", default_rates.get("peak", 0.35)
                )
                data[CONF_SHOULDER_RATE] = detected_rates.get(
                    "shoulder", default_rates.get("shoulder", 0.25)
                )
                data[CONF_OFF_PEAK_RATE] = detected_rates.get(
                    "off_peak", default_rates.get("off_peak", 0.18)
                )
                data[CONF_EV_RATE] = detected_rates.get(
                    "ev", default_rates.get("ev", 0.06)
                )
                data[CONF_FLAT_RATE] = detected_rates.get(
                    "flat", default_rates.get("flat", 0.28)
                )

                return self.async_create_entry(title=self._auth_data["title"], data=data)

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.error("Unexpected config-flow failure")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders=_DESCRIPTION_PLACEHOLDERS,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle reauth when credentials expire."""
        entry_id = self.context.get("entry_id")
        self._reauth_entry = (
            self.hass.config_entries.async_get_entry(entry_id) if entry_id else None
        )
        self._auth_data = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauth credential input."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(
                    self.hass,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
                reauth_entry = self._reauth_entry
                if reauth_entry is None:
                    return self.async_abort(reason="reauth_failed")
                # Reject credentials that belong to a different OVO account —
                # the entry's unique_id (and all sensor unique_ids) are bound
                # to the original account
                if (
                    reauth_entry.unique_id
                    and info["account_id"] != reauth_entry.unique_id
                ):
                    return self.async_abort(reason="reauth_account_mismatch")
                # Update the existing entry with new credentials
                self.hass.config_entries.async_update_entry(
                    reauth_entry,
                    data={
                        **self._auth_data,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_ACCOUNT_ID: info["account_id"],
                    },
                )
                await self.hass.config_entries.async_reload(reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.error("Unexpected reauthentication failure")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders=_DESCRIPTION_PLACEHOLDERS,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for OVO Energy Australia."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            options = {CONF_PLAN_TYPE: user_input[CONF_PLAN_TYPE]}

            # Billing cycle start day applies to every plan type.
            options[CONF_BILLING_CYCLE_DAY] = int(
                user_input.get(CONF_BILLING_CYCLE_DAY, 1)
            )

            # Update rates based on plan type
            plan_type = user_input[CONF_PLAN_TYPE]
            default_rates = DEFAULT_RATES.get(plan_type, {})

            peak_start = int(user_input.get(CONF_PEAK_START_HOUR, 0))
            peak_end = int(user_input.get(CONF_PEAK_END_HOUR, 0))
            has_peak_window = peak_start != peak_end

            if plan_type in (PLAN_FREE_3, PLAN_FREE_4):
                options[CONF_PEAK_RATE] = user_input.get(CONF_PEAK_RATE, default_rates.get("peak", 0.35))
                options[CONF_SHOULDER_RATE] = user_input.get(CONF_SHOULDER_RATE, default_rates.get("shoulder", 0.25))
                options[CONF_OFF_PEAK_RATE] = user_input.get(CONF_OFF_PEAK_RATE, default_rates.get("off_peak", 0.18))
                options[CONF_PEAK_START_HOUR] = peak_start
                options[CONF_PEAK_END_HOUR] = peak_end
            elif plan_type == PLAN_EV:
                options[CONF_PEAK_RATE] = user_input.get(CONF_PEAK_RATE, default_rates.get("peak", 0.35))
                options[CONF_SHOULDER_RATE] = user_input.get(CONF_SHOULDER_RATE, default_rates.get("shoulder", 0.25))
                options[CONF_OFF_PEAK_RATE] = user_input.get(CONF_OFF_PEAK_RATE, default_rates.get("off_peak", 0.18))
                options[CONF_EV_RATE] = user_input.get(CONF_EV_RATE, default_rates.get("ev", 0.06))
                options[CONF_PEAK_START_HOUR] = peak_start
                options[CONF_PEAK_END_HOUR] = peak_end
            elif plan_type == PLAN_BASIC:
                options[CONF_PEAK_RATE] = user_input.get(CONF_PEAK_RATE, default_rates.get("peak", 0.35))
                options[CONF_SHOULDER_RATE] = user_input.get(CONF_SHOULDER_RATE, default_rates.get("shoulder", 0.25))
                options[CONF_OFF_PEAK_RATE] = user_input.get(CONF_OFF_PEAK_RATE, default_rates.get("off_peak", 0.18))
                options[CONF_PEAK_START_HOUR] = peak_start
                options[CONF_PEAK_END_HOUR] = peak_end
            elif plan_type == PLAN_ONE:
                options[CONF_FLAT_RATE] = user_input.get(CONF_FLAT_RATE, default_rates.get("flat", 0.28))
                # The One Plan may be flat or TOU depending on distributor.
                # Keep the flat-plan surface clean unless a TOU window is set.
                if has_peak_window:
                    options[CONF_PEAK_RATE] = user_input.get(CONF_PEAK_RATE, 0.35)
                    options[CONF_SHOULDER_RATE] = user_input.get(CONF_SHOULDER_RATE, 0.25)
                    options[CONF_OFF_PEAK_RATE] = user_input.get(CONF_OFF_PEAK_RATE, 0.18)
                    options[CONF_PEAK_START_HOUR] = peak_start
                    options[CONF_PEAK_END_HOUR] = peak_end

            return self.async_create_entry(title="", data=options)

        # Get current plan settings or use defaults
        current = {**self.config_entry.data, **self.config_entry.options}
        current_plan = current.get(CONF_PLAN_TYPE, PLAN_BASIC)
        runtime_data = getattr(self.config_entry, "runtime_data", None)
        if runtime_data is not None and CONF_PLAN_TYPE not in self.config_entry.options:
            current_plan = runtime_data.plan_config.plan_type
        current_peak = current.get(CONF_PEAK_RATE, 0.35)
        current_shoulder = current.get(CONF_SHOULDER_RATE, 0.25)
        current_off_peak = current.get(CONF_OFF_PEAK_RATE, 0.18)
        current_ev = current.get(CONF_EV_RATE, 0.06)
        current_flat = current.get(CONF_FLAT_RATE, 0.28)
        current_peak_start = current.get(CONF_PEAK_START_HOUR, 0)
        current_peak_end = current.get(CONF_PEAK_END_HOUR, 0)
        current_billing_cycle_day = current.get(CONF_BILLING_CYCLE_DAY, 1)

        # Build options schema
        schema_fields = {
            vol.Required(CONF_PLAN_TYPE, default=current_plan): vol.In({
                PLAN_FREE_3: PLAN_NAMES[PLAN_FREE_3],
                PLAN_FREE_4: PLAN_NAMES[PLAN_FREE_4],
                PLAN_EV: PLAN_NAMES[PLAN_EV],
                PLAN_BASIC: PLAN_NAMES[PLAN_BASIC],
                PLAN_ONE: PLAN_NAMES[PLAN_ONE],
            }),
            vol.Optional(CONF_PEAK_RATE, default=current_peak): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_SHOULDER_RATE, default=current_shoulder): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_OFF_PEAK_RATE, default=current_off_peak): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_EV_RATE, default=current_ev): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_FLAT_RATE, default=current_flat): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            # Billing cycle start day (1-31). 1 keeps the calendar-month behaviour.
            vol.Optional(CONF_BILLING_CYCLE_DAY, default=current_billing_cycle_day): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=31)
            ),
        }
        # OVO does not expose distributor-specific schedule boundaries. The
        # same optional window drives both Current Tariff Period and recovery
        # of hourly entries that the API reports only as OTHER.
        schema_fields[vol.Optional(CONF_PEAK_START_HOUR, default=current_peak_start)] = vol.All(
            vol.Coerce(int), vol.Range(min=0, max=23)
        )
        schema_fields[vol.Optional(CONF_PEAK_END_HOUR, default=current_peak_end)] = vol.All(
            vol.Coerce(int), vol.Range(min=0, max=23)
        )
        options_schema = vol.Schema(schema_fields)

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            description_placeholders=_DESCRIPTION_PLACEHOLDERS,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
