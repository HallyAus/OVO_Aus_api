"""Coordinator regression tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.ovo_energy_au.const import PLAN_FREE_4, PLAN_ONE
from custom_components.ovo_energy_au.coordinator import (
    OVOEnergyAUDataUpdateCoordinator,
)
from custom_components.ovo_energy_au.models import PlanConfig

_GOOD_HOURLY_DATA = {
    "solar": [],
    "export": [
        {
            "periodFrom": "2026-03-19T00:00:00Z",
            "periodTo": "2026-03-19T01:00:00Z",
            "consumption": 1.25,
            "charge": None,
            "rates": None,
        }
    ],
}


def _client_with_hourly_results(results: list) -> MagicMock:
    """Return a fully stubbed client whose hourly calls follow ``results``."""
    client = MagicMock()
    client.get_interval_data = AsyncMock(return_value={})
    client.get_product_agreements = AsyncMock(
        return_value={"productAgreements": []}
    )
    client.get_hourly_data = AsyncMock(side_effect=results)
    client.get_statements = AsyncMock(return_value={})
    client.get_account_extras = AsyncMock(return_value={})
    client.get_vehicle_data = AsyncMock(return_value=[])
    client.get_billing_overview = AsyncMock(return_value={})
    client.get_contact_info = AsyncMock(return_value={"accounts": []})
    client.get_usage_info = AsyncMock(return_value={})
    return client


@pytest.mark.asyncio
async def test_refresh_updates_an_auto_detected_plan_after_account_switch():
    client = _client_with_hourly_results([_GOOD_HOURLY_DATA])
    client.get_product_agreements.return_value = {
        "productAgreements": [
            {"product": {"displayName": "The Free 4 Plan"}}
        ]
    }
    plan_config = PlanConfig(plan_type=PLAN_ONE)
    coordinator = OVOEnergyAUDataUpdateCoordinator(
        MagicMock(), client, "account", plan_config, auto_detect_plan=True
    )

    await coordinator._async_update_data()

    assert plan_config.plan_type == PLAN_FREE_4


@pytest.mark.asyncio
async def test_refresh_preserves_an_explicit_plan_override():
    client = _client_with_hourly_results([_GOOD_HOURLY_DATA])
    client.get_product_agreements.return_value = {
        "productAgreements": [
            {"product": {"displayName": "The Free 4 Plan"}}
        ]
    }
    plan_config = PlanConfig(plan_type=PLAN_ONE)
    coordinator = OVOEnergyAUDataUpdateCoordinator(
        MagicMock(), client, "account", plan_config, auto_detect_plan=False
    )

    await coordinator._async_update_data()

    assert plan_config.plan_type == PLAN_ONE


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
    client.get_contact_info = AsyncMock(
        return_value={
            "accounts": [
                {"id": "account", "customerId": "customer", "closed": False}
            ]
        }
    )
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
    client.get_contact_info = AsyncMock(
        return_value={
            "accounts": [
                {"id": "account", "customerId": "customer", "closed": False}
            ]
        }
    )
    client.get_usage_info = AsyncMock(return_value={})

    coordinator = OVOEnergyAUDataUpdateCoordinator(
        MagicMock(), client, "account", PlanConfig()
    )
    result = await coordinator._async_update_data()

    assert result["flex"]["onboarded"] is False
    assert result["vehicles"] == [vehicle]
    client.get_vehicle_data.assert_awaited_once_with("account", "customer")
    assert result["vehicle_status"] == "available"


@pytest.mark.asyncio
async def test_contact_data_never_falls_back_to_a_different_active_account():
    client = _client_with_hourly_results([_GOOD_HOURLY_DATA])
    client.get_contact_info.return_value = {
        "accounts": [
            {
                "id": "other-account",
                "customerId": "other-customer",
                "customerOrientatedBalance": 999,
                "hasSolar": True,
                "closed": False,
            }
        ]
    }
    coordinator = OVOEnergyAUDataUpdateCoordinator(
        MagicMock(), client, "expected-account", PlanConfig()
    )

    result = await coordinator._async_update_data()

    assert result["account_balance"] is None
    assert result["has_solar"] is None
    client.get_vehicle_data.assert_awaited_once_with("expected-account", None)


@pytest.mark.asyncio
async def test_hourly_exception_reuses_last_good_payload_without_zeroing():
    client = _client_with_hourly_results(
        [_GOOD_HOURLY_DATA, RuntimeError("transient failure")]
    )
    coordinator = OVOEnergyAUDataUpdateCoordinator(
        MagicMock(), client, "account", PlanConfig()
    )

    first = await coordinator._async_update_data()
    last_success = coordinator.hourly_last_success_time
    second = await coordinator._async_update_data()

    assert first["hourly"]["grid_total"] == 1.25
    assert second["hourly"] == first["hourly"]
    assert coordinator.hourly_data_status == "stale"
    assert coordinator.hourly_data_stale is True
    assert coordinator.hourly_data_issue == "fetch_error"
    assert coordinator.hourly_last_success_time == last_success


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "empty_response",
    [{}, {"solar": [], "export": []}, None],
)
async def test_structurally_empty_hourly_response_reuses_last_good_payload(
    empty_response,
):
    client = _client_with_hourly_results([_GOOD_HOURLY_DATA, empty_response])
    coordinator = OVOEnergyAUDataUpdateCoordinator(
        MagicMock(), client, "account", PlanConfig()
    )

    first = await coordinator._async_update_data()
    second = await coordinator._async_update_data()

    assert second["hourly"] == first["hourly"]
    assert coordinator.hourly_data_status == "stale"
    assert coordinator.hourly_data_stale is True
    assert coordinator.hourly_data_issue == "empty_response"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cold_start_result",
    [{}, {"solar": [], "export": []}, None, RuntimeError("transient failure")],
)
async def test_cold_start_unusable_hourly_data_stays_unavailable(cold_start_result):
    client = _client_with_hourly_results([cold_start_result])
    coordinator = OVOEnergyAUDataUpdateCoordinator(
        MagicMock(), client, "account", PlanConfig()
    )

    result = await coordinator._async_update_data()

    assert "hourly" not in result
    assert coordinator.hourly_data_status == "unavailable"
    assert coordinator.hourly_data_stale is False
    assert coordinator.hourly_last_success_time is None
    expected_issue = (
        "fetch_error" if isinstance(cold_start_result, Exception) else "empty_response"
    )
    assert coordinator.hourly_data_issue == expected_issue


@pytest.mark.asyncio
async def test_hourly_status_recovers_after_a_good_response():
    client = _client_with_hourly_results([_GOOD_HOURLY_DATA, {}, _GOOD_HOURLY_DATA])
    coordinator = OVOEnergyAUDataUpdateCoordinator(
        MagicMock(), client, "account", PlanConfig()
    )

    await coordinator._async_update_data()
    await coordinator._async_update_data()
    recovered = await coordinator._async_update_data()

    assert recovered["hourly"]["grid_total"] == 1.25
    assert coordinator.hourly_data_status == "fresh"
    assert coordinator.hourly_data_stale is False
    assert coordinator.hourly_data_issue is None
