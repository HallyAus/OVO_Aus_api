"""Actual Home Assistant entity and config-entry lifecycle contracts."""
from datetime import datetime
from unittest.mock import patch

import jwt
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from packaging.specifiers import SpecifierSet

from custom_components.ovo_energy_au import CONFIG_SCHEMA
from custom_components.ovo_energy_au.api import OVOEnergyAUApiClientAuthenticationError
from custom_components.ovo_energy_au.const import AU_TIMEZONE, DOMAIN


def test_core_pyjwt_satisfies_the_supported_dependency_contract():
    """The real HA environment must supply the range omitted from manifest.json."""
    # Intentionally >=2.13.0: HA core pins PyJWT==2.13.0; the >=2.14.0 floor lives only in pyproject.toml.
    assert jwt.__version__ in SpecifierSet(">=2.13.0,<3.0.0")


async def test_config_entry_schema_reports_unsupported_yaml_without_authentication(hass, caplog):
    """UI setup stays supported; a YAML domain is explained instead of interpreted."""
    config = {"default_config": {}}
    assert CONFIG_SCHEMA(config) == config
    assert "does not support YAML setup" not in caplog.text

    yaml_config = {**config, DOMAIN: {}}
    assert CONFIG_SCHEMA(yaml_config) == yaml_config
    assert f"The {DOMAIN} integration does not support YAML setup" in caplog.text
    assert not hass.config_entries.async_entries(DOMAIN)


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

async def test_old_billing_devices_are_reused(hass, entry, client):
    """Category labels may change, but the device registry identity must not."""
    from homeassistant.helpers import device_registry as dr

    devices = dr.async_get(hass)
    registry = er.async_get(hass)
    old_devices = {
        old: devices.async_get_or_create(
            config_entry_id=entry.entry_id, identifiers={(DOMAIN, f"fixture-account_{old}")}
        )
        for old in ("Last Month", "Month to Date")
    }
    with patch("custom_components.ovo_energy_au.OVOEnergyAUApiClient", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    for prefix, old in (("last_month_", "Last Month"), ("month_to_date_", "Month to Date")):
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"fixture-account_{prefix}grid_consumption")
        assert registry.async_get(entity_id).device_id == old_devices[old].id
    assert not any((DOMAIN, "fixture-account_Last Billing Month") in device.identifiers
                   for device in dr.async_entries_for_config_entry(devices, entry.entry_id))
    await hass.config_entries.async_unload(entry.entry_id)


async def test_ev_entries_survive_discovery_failure_and_recover(hass, entry, client):
    from custom_components.ovo_energy_au.sensor import _EV_SENSOR_KEYS

    registry = er.async_get(hass)
    for key in _EV_SENSOR_KEYS:
        registry.async_get_or_create("sensor", DOMAIN, f"fixture-account_{key}", config_entry=entry)
    client.get_vehicle_data.side_effect = RuntimeError("discovery unavailable")
    with patch("custom_components.ovo_energy_au.OVOEnergyAUApiClient", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        for key in _EV_SENSOR_KEYS:
            entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"fixture-account_{key}")
            assert entity_id is not None
            assert hass.states.get(entity_id) is not None
        client.get_vehicle_data.side_effect = None
        client.get_vehicle_data.return_value = [{"id": "test-vehicle"}]
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        for key in _EV_SENSOR_KEYS:
            entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"fixture-account_{key}")
            assert hass.states.get(entity_id) is not None
        await hass.config_entries.async_unload(entry.entry_id)
