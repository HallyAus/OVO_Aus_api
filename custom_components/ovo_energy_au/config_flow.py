"""Config flow for OVO Energy Australia integration."""
from __future__ import annotations

import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, CONF_ACCESS_TOKEN, CONF_ID_TOKEN, CONF_ACCOUNT_ID, CONF_REFRESH_TOKEN
from .ovo_client import OVOEnergyAU, OVOAPIError

_LOGGER = logging.getLogger(__name__)

# Authentication method selection
AUTH_METHOD_PASSWORD = "password"
AUTH_METHOD_TOKENS = "tokens"
AUTH_METHOD_JSON = "json"

STEP_AUTH_METHOD_SCHEMA = vol.Schema(
    {
        vol.Required("auth_method", default=AUTH_METHOD_JSON): vol.In({
            AUTH_METHOD_JSON: "Paste OAuth Response (Easiest - copy JSON from browser)",
            AUTH_METHOD_PASSWORD: "Username & Password (Automatic)",
            AUTH_METHOD_TOKENS: "Manual Token Entry (Advanced)"
        })
    }
)

STEP_PASSWORD_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
        vol.Optional(CONF_ACCOUNT_ID): str,
    }
)

STEP_JSON_SCHEMA = vol.Schema(
    {
        vol.Required("oauth_response"): str,
        vol.Optional(CONF_ACCOUNT_ID): str,
    }
)

STEP_TOKENS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): str,
        vol.Required(CONF_ID_TOKEN): str,
        vol.Required(CONF_REFRESH_TOKEN): str,
        vol.Required(CONF_ACCOUNT_ID): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    _LOGGER.debug("Validating OVO Energy credentials for account %s", data[CONF_ACCOUNT_ID])

    # Create client and test authentication
    client = OVOEnergyAU(
        account_id=data[CONF_ACCOUNT_ID],
        refresh_token=data.get(CONF_REFRESH_TOKEN)
    )
    client.set_tokens(
        data[CONF_ACCESS_TOKEN],
        data[CONF_ID_TOKEN],
        data.get(CONF_REFRESH_TOKEN)
    )

    try:
        # Test the connection by fetching data
        _LOGGER.debug("Testing API connection...")
        result = await hass.async_add_executor_job(client.get_today_data)
        _LOGGER.debug("API connection successful, received data: %s", result)
    except OVOAPIError as err:
        _LOGGER.error("Failed to authenticate with OVO Energy API: %s", err)
        raise InvalidAuth from err
    except Exception as err:
        _LOGGER.exception("Unexpected exception during validation")
        raise CannotConnect from err
    finally:
        client.close()

    # Return info to be stored in the config entry
    return {"title": f"OVO Energy AU ({data[CONF_ACCOUNT_ID]})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OVO Energy Australia."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._auth_method: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - choose authentication method."""
        if user_input is not None:
            self._auth_method = user_input["auth_method"]

            if self._auth_method == AUTH_METHOD_JSON:
                return await self.async_step_json()
            elif self._auth_method == AUTH_METHOD_PASSWORD:
                return await self.async_step_password()
            else:
                return await self.async_step_tokens()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_AUTH_METHOD_SCHEMA,
            description_placeholders={
                "json_hint": "Find oauth/token in Network tab → Response",
                "password_hint": "Your OVO account credentials",
                "tokens_hint": "For advanced users only"
            }
        )

    async def async_step_json(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle OAuth JSON paste authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Parse the OAuth response JSON
                oauth_data = json.loads(user_input["oauth_response"])

                # Extract tokens
                access_token = oauth_data.get("access_token")
                id_token = oauth_data.get("id_token")
                refresh_token = oauth_data.get("refresh_token")

                # Extract account_id from JSON if present, otherwise from form
                account_id = oauth_data.get("account_id") or user_input.get(CONF_ACCOUNT_ID)

                if not access_token or not id_token:
                    errors["oauth_response"] = "invalid_json_missing_tokens"
                elif not account_id:
                    errors[CONF_ACCOUNT_ID] = "missing_account_id"
                else:
                    # Add Bearer prefix if not present
                    if not access_token.startswith("Bearer "):
                        access_token = f"Bearer {access_token}"

                    # Create data dict
                    data = {
                        CONF_ACCESS_TOKEN: access_token,
                        CONF_ID_TOKEN: id_token,
                        CONF_REFRESH_TOKEN: refresh_token,
                        CONF_ACCOUNT_ID: account_id,
                    }

                    # Validate the tokens work
                    info = await validate_input(self.hass, data)

                    # Create a unique ID based on account ID
                    await self.async_set_unique_id(data[CONF_ACCOUNT_ID])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(title=info["title"], data=data)

            except json.JSONDecodeError:
                errors["oauth_response"] = "invalid_json"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="json",
            data_schema=STEP_JSON_SCHEMA,
            errors=errors,
            description_placeholders={
                "instructions": "1. Open browser DevTools (F12)\n2. Find oauth/token request in Network tab\n3. Copy the entire Response JSON\n4. Add \"account_id\": \"YOUR_ID\" to the JSON (or enter separately below)"
            }
        )

    async def async_step_password(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle username/password authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                _LOGGER.info("Attempting username/password authentication")

                # Create client without account_id initially
                client = OVOEnergyAU()

                # Run authentication in executor
                success = await self.hass.async_add_executor_job(
                    client.authenticate,
                    user_input["username"],
                    user_input["password"]
                )

                if success:
                    _LOGGER.info("Authentication succeeded, extracting tokens and account_id...")

                    # Get account_id from user input or extract from client
                    account_id = user_input.get(CONF_ACCOUNT_ID) or client.account_id

                    if not account_id:
                        _LOGGER.error("Could not determine account_id after authentication")
                        errors["base"] = "missing_account_id"
                    else:
                        # Extract tokens from client
                        data = {
                            CONF_ACCESS_TOKEN: client._access_token,
                            CONF_ID_TOKEN: client._id_token,
                            CONF_REFRESH_TOKEN: client._refresh_token,
                            CONF_ACCOUNT_ID: account_id,
                        }

                        _LOGGER.info("Account ID extracted: %s", account_id)
                        _LOGGER.debug("Tokens extracted: access_token=%s..., id_token=%s...",
                                     data[CONF_ACCESS_TOKEN][:50] if data[CONF_ACCESS_TOKEN] else None,
                                     data[CONF_ID_TOKEN][:50] if data[CONF_ID_TOKEN] else None)

                        # Validate
                        info = await validate_input(self.hass, data)

                        # Create entry
                        await self.async_set_unique_id(data[CONF_ACCOUNT_ID])
                        self._abort_if_unique_id_configured()

                        client.close()
                        return self.async_create_entry(title=info["title"], data=data)
                else:
                    _LOGGER.error("Authentication returned False - credentials invalid")
                    errors["base"] = "invalid_auth"

            except OVOAPIError as err:
                _LOGGER.error("API error during authentication: %s", err)
                errors["base"] = "cannot_connect"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected authentication error: %s", err)
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="password",
            data_schema=STEP_PASSWORD_SCHEMA,
            errors=errors,
            description_placeholders={
                "hint": "Account ID will be extracted automatically from your login"
            }
        )

    async def async_step_tokens(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual token entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Add Bearer prefix to access token if not present
                access_token = user_input[CONF_ACCESS_TOKEN]
                if not access_token.startswith("Bearer "):
                    access_token = f"Bearer {access_token}"
                    user_input[CONF_ACCESS_TOKEN] = access_token

                info = await validate_input(self.hass, user_input)

                # Create a unique ID based on account ID
                await self.async_set_unique_id(user_input[CONF_ACCOUNT_ID])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=user_input)

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="tokens",
            data_schema=STEP_TOKENS_SCHEMA,
            errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
