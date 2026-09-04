"""Real HA fixtures, separate from the unit suite's mocked HA modules."""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ovo_energy_au.const import AU_TIMEZONE, DOMAIN


@pytest.fixture(autouse=True)
def enable_ovo(enable_custom_integrations):
    yield


@pytest.fixture
def client():
    now = datetime.now(AU_TIMEZONE)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    yesterday = (now - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0).isoformat()
    client = MagicMock()
    client.authenticate_with_password = AsyncMock(return_value={})
    client.get_interval_data = AsyncMock(return_value={
        "monthly": {"export": [{"periodFrom": start, "consumption": 12.5,
                                 "charge": {"type": "DEBIT", "value": 3.75}}]}})
    client.get_hourly_data = AsyncMock(return_value={"export": [{"periodFrom": yesterday, "consumption": 1,
                                                               "charge": None, "rates": None}]})
    client.get_product_agreements = AsyncMock(return_value={"productAgreements": [{"product": {
        "displayName": "The Basic Plan", "unitRatesCentsPerKWH": {"peak": 35}}}]})
    for name in ("get_statements", "get_account_extras", "get_billing_overview", "get_usage_info"):
        setattr(client, name, AsyncMock(return_value={}))
    client.get_contact_info = AsyncMock(return_value={"accounts": []})
    client.get_vehicle_data = AsyncMock(return_value=[])
    return client


@pytest.fixture
def entry(hass):
    result = MockConfigEntry(domain=DOMAIN, title="OVO Fixture", unique_id="fixture-account",
                            data={"username": "fixture@example.invalid", "password": "fixture-password",
                                  "account_id": "fixture-account", "plan_type": "basic"})
    result.add_to_hass(hass)
    return result


@pytest.fixture
async def loaded(hass, entry, client):
    with patch("custom_components.ovo_energy_au.OVOEnergyAUApiClient", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry.runtime_data
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
