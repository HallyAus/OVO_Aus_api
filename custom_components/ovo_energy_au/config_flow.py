"""Config flow for OVO Energy Australia integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, CONF_ACCESS_TOKEN, CONF_ID_TOKEN, CONF_ACCOUNT_ID
from .ovo_client import OVOEnergyAU, OVOAPIError

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): str,
        vol.Required(CONF_ID_TOKEN): str,
        vol.Required(CONF_ACCOUNT_ID): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    _LOGGER.debug("Validating OVO Energy credentials for account %s", data[CONF_ACCOUNT_ID])

    # Create client and test authentication
    client = OVOEnergyAU(account_id=data[CONF_ACCOUNT_ID])
    client.set_tokens(data[CONF_ACCESS_TOKEN], data[CONF_ID_TOKEN])

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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Create a unique ID based on account ID to prevent duplicates
                await self.async_set_unique_id(user_input[CONF_ACCOUNT_ID])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
