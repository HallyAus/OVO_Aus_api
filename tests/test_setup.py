"""Integration lifecycle regression tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ovo_energy_au import (
    async_remove_config_entry_device,
    async_setup,
    async_setup_entry,
)
from custom_components.ovo_energy_au.const import DOMAIN


@pytest.mark.asyncio
async def test_setup_entry_uses_runtime_data_and_options_override():
    hass = MagicMock()
    setup_order = []

    async def record_platform_setup(*args):
        setup_order.append("platform")

    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_forward_entry_setups.side_effect = record_platform_setup
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
    device_registry = MagicMock()
    def create_account_device(**kwargs):
        setup_order.append("account_device")
        return SimpleNamespace(id="account-device-id")

    device_registry.async_get_or_create.side_effect = create_account_device

    with (
        patch("custom_components.ovo_energy_au.async_get_clientsession"),
        patch(
            "custom_components.ovo_energy_au.dr.async_get",
            return_value=device_registry,
        ),
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
    assert coordinator_class.call_args.kwargs["auto_detect_plan"] is True
    device_registry.async_get_or_create.assert_called_once_with(
        config_entry_id="entry-id",
        identifiers={(DOMAIN, "account")},
        name="OVO Energy AU",
        manufacturer="OVO Energy Australia",
        model="Energy Monitor",
    )
    assert setup_order == ["account_device", "platform"]
    assert coordinator.account_device_id == "account-device-id"
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


@pytest.mark.asyncio
async def test_setup_entry_consolidate_devices_removes_orphaned_devices():
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    entry = SimpleNamespace(
        data={
            "username": "person@example.com",
            "password": "test-password",  # pragma: allowlist secret
            "account_id": "12345",
        },
        options={"consolidate_devices": True},
        runtime_data=None,
        entry_id="entry-123",
        async_on_unload=MagicMock(),
        add_update_listener=MagicMock(),
    )
    client = MagicMock()
    client.authenticate_with_password = AsyncMock()
    coordinator = MagicMock()
    coordinator.consolidate_devices = True
    coordinator.async_config_entry_first_refresh = AsyncMock()

    account_device = SimpleNamespace(id="account-device-id")
    orphan_device = SimpleNamespace(id="orphan-category-device")
    active_child_device = SimpleNamespace(id="child-with-entities")

    dev_reg = MagicMock()
    dev_reg.async_get_or_create.return_value = account_device

    ent_reg = MagicMock()

    # orphan_device has no entities; active_child_device has 1 entity
    def entries_for_device(registry, dev_id):
        if dev_id == "child-with-entities":
            return [SimpleNamespace(entity_id="sensor.child")]
        return []

    with (
        patch("custom_components.ovo_energy_au.async_get_clientsession"),
        patch("custom_components.ovo_energy_au.dr.async_get", return_value=dev_reg),
        patch(
            "custom_components.ovo_energy_au.dr.async_entries_for_config_entry",
            return_value=[account_device, orphan_device, active_child_device],
        ),
        patch("custom_components.ovo_energy_au.er.async_get", return_value=ent_reg),
        patch(
            "custom_components.ovo_energy_au.er.async_entries_for_device",
            side_effect=entries_for_device,
        ),
        patch(
            "custom_components.ovo_energy_au.OVOEnergyAUApiClient",
            return_value=client,
        ),
        patch(
            "custom_components.ovo_energy_au.OVOEnergyAUDataUpdateCoordinator",
            return_value=coordinator,
        ),
    ):
        assert await async_setup_entry(hass, entry) is True

    # Account device is not removed, child with entities is not removed, empty orphan is removed
    dev_reg.async_remove_device.assert_called_once_with("orphan-category-device")


@pytest.mark.asyncio
async def test_async_remove_config_entry_device():
    hass = MagicMock()
    entry = SimpleNamespace(entry_id="entry-123")
    device_entry = SimpleNamespace(id="dev-123")
    assert await async_remove_config_entry_device(hass, entry, device_entry) is True


def test_retired_sensor_keys_include_legacy_orphans():
    from custom_components.ovo_energy_au.sensor import (
        _RETIRED_SENSOR_KEYS,
        _remove_retired_registry_entities,
    )

    expected_keys = {
        "hourly_solar_consumption",
        "hourly_grid_consumption",
        "hourly_return_to_grid",
        "tou_shoulder_consumption",
        "super_off_peak_consumption",
        "super_off_peak_cost_saved",
        "ev_off_peak_weekly_consumption",
        "ev_off_peak_weekly_cost",
        "ev_off_peak_weekly_savings",
        "ev_off_peak_monthly_consumption",
        "ev_off_peak_monthly_cost",
        "ev_off_peak_monthly_savings",
        "ev_off_peak_yearly_consumption",
        "ev_off_peak_yearly_cost",
        "ev_off_peak_yearly_savings",
    }
    assert expected_keys.issubset(_RETIRED_SENSOR_KEYS)

    hass = MagicMock()
    entry = SimpleNamespace(entry_id="entry-123")
    registry = MagicMock()

    test_entries = [
        SimpleNamespace(
            entity_id="sensor.ovo_energy_au_hourly_data_last_7_days_solar_consumption",
            unique_id="12345_hourly_solar_consumption",
        ),
        SimpleNamespace(
            entity_id="sensor.ovo_energy_au_daily_solar_consumption",
            unique_id="12345_daily_solar_consumption",
        ),
    ]

    with (
        patch(
            "custom_components.ovo_energy_au.sensor.er.async_get",
            return_value=registry,
        ),
        patch(
            "custom_components.ovo_energy_au.sensor.er.async_entries_for_config_entry",
            return_value=test_entries,
        ),
    ):
        _remove_retired_registry_entities(hass, entry, "12345")

    registry.async_remove.assert_called_once_with(
        "sensor.ovo_energy_au_hourly_data_last_7_days_solar_consumption"
    )

