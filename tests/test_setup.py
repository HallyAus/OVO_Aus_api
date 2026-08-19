"""Integration lifecycle regression tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ovo_energy_au import async_setup, async_setup_entry
from custom_components.ovo_energy_au.const import DOMAIN


@pytest.mark.asyncio
async def test_setup_entry_uses_runtime_data_and_options_override():
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_reload = AsyncMock()
    unload_callback = MagicMock()
    update_listener = MagicMock()
    entry = SimpleNamespace(
        data={
            "username": "person@example.com",
            "password": "test-password",  # pragma: allowlist secret
            "account_id": "account",
            "plan_type": "ev",
            "ev_rate": 0.06,
        },
        options={"ev_rate": 0.08, "billing_cycle_day": 14},
        runtime_data=None,
        entry_id="entry-id",
        async_on_unload=unload_callback,
        add_update_listener=MagicMock(return_value=update_listener),
    )
    client = MagicMock()
    client.authenticate_with_password = AsyncMock()
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch("custom_components.ovo_energy_au.async_get_clientsession"),
        patch(
            "custom_components.ovo_energy_au.OVOEnergyAUApiClient",
            return_value=client,
        ),
        patch(
            "custom_components.ovo_energy_au.OVOEnergyAUDataUpdateCoordinator",
            return_value=coordinator,
        ) as coordinator_class,
    ):
        assert await async_setup_entry(hass, entry) is True

    assert entry.runtime_data is coordinator
    plan_config = coordinator_class.call_args.kwargs["plan_config"]
    assert plan_config.ev_rate == 0.08
    assert plan_config.billing_cycle_day == 14
    entry.add_update_listener.assert_called_once()
    update_callback = entry.add_update_listener.call_args.args[0]
    await update_callback(hass, entry)
    hass.config_entries.async_reload.assert_awaited_once_with("entry-id")
    unload_callback.assert_called_once_with(update_listener)
    hass.config_entries.async_forward_entry_setups.assert_awaited_once()


@pytest.mark.asyncio
async def test_integration_service_refreshes_loaded_runtime_coordinators():
    coordinator = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    entry = SimpleNamespace(runtime_data=coordinator)
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [entry]

    assert await async_setup(hass, {}) is True

    domain, service, handler = hass.services.async_register.call_args.args
    assert (domain, service) == (DOMAIN, "refresh_data")
    await handler(MagicMock())
    coordinator.async_request_refresh.assert_awaited_once()
