"""Actual Home Assistant entity and config-entry lifecycle contracts."""
from datetime import datetime
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er

from custom_components.ovo_energy_au.api import OVOEnergyAUApiClientAuthenticationError
from custom_components.ovo_energy_au.const import AU_TIMEZONE, DOMAIN


def entity_id(hass):
    return er.async_get(hass).async_get_entity_id("sensor", DOMAIN, "fixture-account_energy_grid_import")


async def test_setup_reload_and_entity_identity(hass, entry, loaded):
    sensor_id = entity_id(hass)
    state = hass.states.get(sensor_id)
    assert state.state == "12.5"
    assert state.attributes["state_class"] == "total"
    assert state.attributes["unit_of_measurement"] == "kWh"
    assert hass.services.has_service(DOMAIN, "refresh_data")
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED
    assert entity_id(hass) == sensor_id
    assert hass.states.get(sensor_id).state == "12.5"


async def test_delayed_month_keeps_source_reset_epoch(hass, client, loaded):
    client.get_interval_data.return_value = {"monthly": {"export": [
        {"periodFrom": "2000-01-31T13:00:00Z", "consumption": 100, "charge": {"type": "DEBIT", "value": 30}}]}}
    await loaded.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id(hass))
    assert state.state == "100.0"
    assert datetime.fromisoformat(state.attributes["last_reset"]) == datetime(2000, 2, 1, tzinfo=AU_TIMEZONE)


async def test_invalid_period_never_publishes_numeric_total(hass, client, loaded):
    client.get_interval_data.return_value = {"monthly": {"export": [{"consumption": 999}]}}
    await loaded.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id(hass)).state == "unknown"


async def test_setup_timeout_requests_retry_not_reauth(hass, entry, client):
    client.authenticate_with_password.side_effect = TimeoutError("private-provider-detail")
    with patch("custom_components.ovo_energy_au.OVOEnergyAUApiClient", return_value=client):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_rejected_credentials_request_reauth(hass, entry, client):
    client.authenticate_with_password.side_effect = OVOEnergyAUApiClientAuthenticationError("private-provider-detail")
    with patch("custom_components.ovo_energy_au.OVOEnergyAUApiClient", return_value=client):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_ERROR
