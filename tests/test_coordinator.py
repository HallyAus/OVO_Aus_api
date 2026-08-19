"""Coordinator regression tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.ovo_energy_au.coordinator import (
    OVOEnergyAUDataUpdateCoordinator,
)
from custom_components.ovo_energy_au.models import PlanConfig


@pytest.mark.asyncio
async def test_bill_estimate_uses_export_credit_not_solar_generation_charge():
    client = MagicMock()
    client.get_interval_data = AsyncMock(
        return_value={
            "daily": {
                "solar": [
                    {
                        "periodFrom": "2026-03-19T00:00:00Z",
                        "consumption": 12,
                        "charge": {"value": -10, "type": "CREDIT"},
                    }
                ],
                "export": [
                    {
                        "periodFrom": "2026-03-19T00:00:00Z",
                        "consumption": 5,
                        "charge": {"value": 5, "type": "DEBIT"},
                    },
                    {
                        "periodFrom": "2026-03-19T00:00:00Z",
                        "consumption": 2,
                        "charge": {"value": -2, "type": "CREDIT"},
                    },
                ],
            }
        }
    )
    client.get_product_agreements = AsyncMock(return_value={"productAgreements": []})
    client.get_hourly_data = AsyncMock(return_value={})
    client.get_statements = AsyncMock(return_value={})
    client.get_account_extras = AsyncMock(return_value={})
    client.get_vehicle_data = AsyncMock(return_value=[])
    client.get_billing_overview = AsyncMock(return_value={})
    client.get_contact_info = AsyncMock(return_value={"accounts": []})
    client.get_usage_info = AsyncMock(return_value={})

    coordinator = OVOEnergyAUDataUpdateCoordinator(
        MagicMock(), client, "account", PlanConfig()
    )
    result = await coordinator._async_update_data()

    assert result["bill_estimate"]["mtd_grid_cost"] == 5
    assert result["bill_estimate"]["mtd_export_credit"] == 2
    assert result["bill_estimate"]["mtd_bill"] == 3


@pytest.mark.asyncio
async def test_billing_overview_is_added_to_coordinator_data():
    client = MagicMock()
    client.get_interval_data = AsyncMock(return_value={})
    client.get_product_agreements = AsyncMock(return_value={"productAgreements": []})
    client.get_hourly_data = AsyncMock(return_value={})
    client.get_statements = AsyncMock(return_value={})
    client.get_account_extras = AsyncMock(return_value={})
    client.get_vehicle_data = AsyncMock(return_value=[])
    client.get_billing_overview = AsyncMock(
        return_value={
            "billingInformation": {"minimumDirectDebitAmount": 40},
            "unbilledCharges": {"billProgress": 50},
        }
    )
    client.get_contact_info = AsyncMock(return_value={"accounts": []})
    client.get_usage_info = AsyncMock(return_value={})

    coordinator = OVOEnergyAUDataUpdateCoordinator(
        MagicMock(), client, "account", PlanConfig()
    )
    result = await coordinator._async_update_data()

    assert result["billing_information"]["minimumDirectDebitAmount"] == 40
    assert result["unbilled_charges"]["billProgress"] == 50


@pytest.mark.asyncio
async def test_vehicle_discovery_does_not_trust_unrelated_flex_flag():
    client = MagicMock()
    client.get_interval_data = AsyncMock(return_value={})
    client.get_product_agreements = AsyncMock(return_value={"productAgreements": []})
    client.get_hourly_data = AsyncMock(return_value={})
    client.get_statements = AsyncMock(return_value={})
    client.get_account_extras = AsyncMock(
        return_value={"flex": {"hasOnboarded": False}}
    )
    vehicle = {"id": "opaque-vehicle", "name": "Connected EV"}
    client.get_vehicle_data = AsyncMock(return_value=[vehicle])
    client.get_billing_overview = AsyncMock(return_value={})
    client.get_contact_info = AsyncMock(return_value={"accounts": []})
    client.get_usage_info = AsyncMock(return_value={})

    coordinator = OVOEnergyAUDataUpdateCoordinator(
        MagicMock(), client, "account", PlanConfig()
    )
    result = await coordinator._async_update_data()

    assert result["flex"]["onboarded"] is False
    assert result["vehicles"] == [vehicle]
    client.get_vehicle_data.assert_awaited_once_with("account")
