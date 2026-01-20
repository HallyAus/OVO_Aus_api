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

from .const import DOMAIN, CONF_ACCOUNT_ID
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

                # Store username, password, and account_id
                data = {
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_ACCOUNT_ID: info["account_id"],
                }

                # Create unique ID based on account ID
                await self.async_set_unique_id(info["account_id"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=data)

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


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
