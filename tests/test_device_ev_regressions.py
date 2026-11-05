from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from custom_components.ovo_energy_au import sensor as platform
from custom_components.ovo_energy_au.sensors.base import OVOEnergySensor
from custom_components.ovo_energy_au.sensors.definitions import ENERGY_SENSORS


@pytest.mark.parametrize(("prefix", "old", "label"), [
    ("last_month_", "Last Month", "Last Billing Month"),
    ("month_to_date_", "Month to Date", "Billing Month to Date"),
])
def test_billing_devices_keep_historical_identity(prefix, old, label):
    coordinator = SimpleNamespace(account_id="account", consolidate_devices=False, account_device_id="parent")
    definitions = [item for item in ENERGY_SENSORS if item[0].startswith(prefix)]
    assert len(definitions) == 4
    for definition in definitions:
        entity = OVOEnergySensor(coordinator, *definition)
        assert entity.device_info["identifiers"] == {("ovo_energy_au", f"account_{old}")}
        assert entity.device_info["name"] == f"OVO Energy AU - {label}"
        assert entity.device_info["via_device_id"] == "parent"
        assert entity._attr_unique_id == f"account_{definition[0]}"
    coordinator.consolidate_devices = True
    assert entity.device_info["identifiers"] == {("ovo_energy_au", "account")}
    assert label in entity.name


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["unavailable", None])
async def test_discovery_failure_preserves_ev_registry_and_recovers(status):
    coordinator = SimpleNamespace(account_id="account", plan_config=SimpleNamespace(plan_type="basic"),
                                  data={"vehicle_status": status, "vehicles": []},
                                  async_add_listener=MagicMock())
    entry = SimpleNamespace(entry_id="entry", runtime_data=coordinator, async_on_unload=MagicMock())
    registry = MagicMock()
    entries = [SimpleNamespace(unique_id=f"account_{key}", entity_id=f"sensor.{key}")
               for key in platform._EV_SENSOR_KEYS]
    add = MagicMock()
    with (patch.object(platform, "callback", lambda f: f),
          patch.object(platform.er, "async_get", return_value=registry),
          patch.object(platform.er, "async_entries_for_config_entry", return_value=entries)):
        await platform.async_setup_entry(MagicMock(), entry, add)
        registry.async_remove.assert_not_called()
        keys = {entity._sensor_key for entity in add.call_args.args[0] if hasattr(entity, "_sensor_key")}
        assert keys >= platform._EV_SENSOR_KEYS
        coordinator.data = {"vehicle_status": "available", "vehicles": [{"id": "vehicle"}]}
        coordinator.async_add_listener.call_args.args[0]()
        added = add.call_args.args[0]
        assert any(entity._sensor_key.startswith("vehicle_vehicle_") for entity in added)
        assert not any(entity._sensor_key in platform._EV_SENSOR_KEYS for entity in added)


@pytest.mark.asyncio
async def test_confirmed_absence_and_later_ev_discovery():
    coordinator = SimpleNamespace(account_id="account", plan_config=SimpleNamespace(plan_type="basic"),
                                  data={"vehicle_status": "none_found", "vehicles": []},
                                  async_add_listener=MagicMock())
    entry = SimpleNamespace(entry_id="entry", runtime_data=coordinator, async_on_unload=MagicMock())
    registry = MagicMock()
    entries = [SimpleNamespace(unique_id=f"account_{key}", entity_id=f"sensor.{key}")
               for key in platform._EV_SENSOR_KEYS]
    add = MagicMock()
    with (patch.object(platform, "callback", lambda f: f),
          patch.object(platform.er, "async_get", return_value=registry),
          patch.object(platform.er, "async_entries_for_config_entry", return_value=entries)):
        await platform.async_setup_entry(MagicMock(), entry, add)
        assert registry.async_remove.call_count == len(entries)
        keys = {entity._sensor_key for entity in add.call_args.args[0] if hasattr(entity, "_sensor_key")}
        assert not (keys & platform._EV_SENSOR_KEYS)
        coordinator.data = {"vehicle_status": "available", "vehicles": [{"id": "vehicle"}]}
        listener = coordinator.async_add_listener.call_args.args[0]
        listener()
        keys = [entity._sensor_key for entity in add.call_args.args[0]]
        assert set(keys) >= platform._EV_SENSOR_KEYS
        assert len(keys) == len(set(keys))
        listener()
        assert add.call_count == 2
