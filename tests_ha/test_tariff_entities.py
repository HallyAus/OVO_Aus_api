"""Tariff contracts exercised through real Home Assistant entity publication."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import async_get_platforms
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.ovo_energy_au.binary_sensor import OVOFreeEnergyWindowBinarySensor
from custom_components.ovo_energy_au.const import CONF_PLAN_TYPE, DOMAIN, PLAN_FREE_3, PLAN_FREE_4


def _entity_id(hass, key, domain="sensor"):
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"fixture-account_{key}")


def _state(hass, key, domain="sensor"):
    entity_id = _entity_id(hass, key, domain)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state


def _entity(hass, key, domain="sensor"):
    entity_id = _entity_id(hass, key, domain)
    return next(platform.entities[entity_id] for platform in async_get_platforms(hass, DOMAIN)
                if entity_id in platform.entities)


def _assert_tariff_states(hass, inside):
    price = _state(hass, "current_electricity_price")
    assert float(price.state) == pytest.approx(0 if inside else 0.2574)
    assert price.attributes["unit_of_measurement"] == "AUD/kWh"
    assert _state(hass, "current_tariff_period").state == ("Super Off-Peak (FREE)" if inside else "Standard")
    binary = _state(hass, "free_energy_window", "binary_sensor")
    assert binary.state == ("on" if inside else "off")
    assert "unit_of_measurement" not in binary.attributes
    assert "state_class" not in binary.attributes


@pytest.fixture
async def tariff_setup(hass, entry, client):
    """Load actual entities while preventing polls from hiding missing timers."""
    client.get_product_agreements.return_value = {
        "productAgreements": [{"product": {
            "displayName": "The Free 3 Plan",
            "unitRatesCentsPerKWH": {"standard": 25.74, "feedInTariff": 3.3},
        }}],
    }

    async def setup(plan=PLAN_FREE_3, time_zone="Australia/Sydney"):
        await hass.config.async_set_time_zone(time_zone)
        hass.config_entries.async_update_entry(entry, options={CONF_PLAN_TYPE: plan})
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry.runtime_data

    with (
        patch("custom_components.ovo_energy_au.OVOEnergyAUApiClient", return_value=client),
        patch("custom_components.ovo_energy_au.coordinator.OVOEnergyAUDataUpdateCoordinator._schedule_refresh"),
    ):
        yield setup
        if entry.state == ConfigEntryState.LOADED:
            assert await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()


def test_free_window_has_only_binary_sensor_state_semantics():
    """SensorEntity.state must never shadow BinarySensorEntity's on/off state."""
    assert issubclass(OVOFreeEnergyWindowBinarySensor, BinarySensorEntity)
    assert not issubclass(OVOFreeEnergyWindowBinarySensor, SensorEntity)


@pytest.mark.parametrize(("plan", "end_hour"), [(PLAN_FREE_3, 14), (PLAN_FREE_4, 15)])
@pytest.mark.parametrize("inside", [False, True])
async def test_published_binary_state_at_window_boundaries(hass, freezer, tariff_setup, plan, end_hour, inside):
    """The state HA publishes, rather than only is_on, must be an on/off value."""
    now = datetime(2026, 11, 2, 11 if inside else end_hour, tzinfo=ZoneInfo("Australia/Sydney"))
    freezer.move_to(now)
    await tariff_setup(plan)
    assert _state(hass, "free_energy_window", "binary_sensor").state == ("on" if inside else "off")


@pytest.mark.parametrize(("plan", "end_hour"), [(PLAN_FREE_3, 14), (PLAN_FREE_4, 15)])
@pytest.mark.parametrize(("date", "time_zone"), [
    ("2026-11-02", "Australia/Sydney"),  # AEDT, UTC+11
    ("2026-07-02", "Australia/Sydney"),  # AEST, UTC+10
    ("2026-04-04", "Australia/Sydney"),  # Next day crosses the end of DST
    ("2026-10-03", "Australia/Sydney"),  # Next day crosses the start of DST
    ("2026-11-02", "Australia/Adelaide"),  # Half-hour local zone, issue #86
    ("2026-11-02", "Australia/Brisbane"),  # No daylight saving, issue #86
])
async def test_price_updates_at_boundary_without_coordinator_refresh(
    hass, freezer, tariff_setup, client, plan, end_hour, date, time_zone,
):
    """HA's local clock publishes tariff changes independently of UTC/API polls."""
    boundary = datetime.fromisoformat(date).replace(hour=11, tzinfo=ZoneInfo(time_zone))
    freezer.move_to((boundary - timedelta(seconds=1)).astimezone(UTC))
    await tariff_setup(plan, time_zone)
    assert float(_state(hass, "current_electricity_price").state) == pytest.approx(0.2574)
    api_calls = list(client.mock_calls)
    end = boundary.replace(hour=end_hour)
    checkpoints = [
        (boundary, True),
        (boundary.replace(hour=14), plan == PLAN_FREE_4),
        (end, False),
        (boundary + timedelta(days=1), True),
        (end + timedelta(days=1), False),
    ]
    for now, inside in checkpoints:
        freezer.move_to(now.astimezone(UTC))
        # The official helper accommodates HA's deliberate 0.05–0.5s event
        # scheduler jitter. No five-minute coordinator update is allowed.
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
        _assert_tariff_states(hass, inside)
    assert client.mock_calls == api_calls


@pytest.mark.parametrize(("plan", "end_hour"), [(PLAN_FREE_3, 14), (PLAN_FREE_4, 15)])
async def test_one_second_before_end_is_still_free(hass, freezer, tariff_setup, plan, end_hour):
    """End is exclusive, with a truthful fractional hours_remaining attribute."""
    now = datetime(2026, 11, 2, end_hour - 1, 59, 59, tzinfo=ZoneInfo("Australia/Sydney"))
    freezer.move_to(now)
    await tariff_setup(plan)
    _assert_tariff_states(hass, True)
    state = _state(hass, "free_energy_window", "binary_sensor")
    assert state.attributes["hours_remaining"] == pytest.approx(1 / 3600)


@pytest.mark.parametrize("plan", [PLAN_FREE_3, PLAN_FREE_4])
async def test_zero_ordinary_rate_does_not_activate_the_free_window(hass, freezer, tariff_setup, client, plan):
    """A zero import rate outside the advertised window is not a window signal."""
    freezer.move_to(datetime(2026, 11, 2, 10, tzinfo=ZoneInfo("Australia/Sydney")))
    client.get_product_agreements.return_value["productAgreements"][0]["product"]["unitRatesCentsPerKWH"]["standard"] = 0
    await tariff_setup(plan)
    assert float(_state(hass, "current_electricity_price").state) == 0
    assert _state(hass, "free_energy_window", "binary_sensor").state == "off"


async def test_numeric_price_and_solar_feed_in_tariff_publish_real_ha_states(hass, freezer, tariff_setup):
    """Home Assistant accepts and publishes both per-kWh monetary entities."""
    freezer.move_to(datetime(2026, 11, 2, 10, tzinfo=ZoneInfo("Australia/Sydney")))
    await tariff_setup()
    for key, expected in (("current_electricity_price", 0.2574), ("solar_feed_in_tariff", 0.033)):
        state = _state(hass, key)
        assert float(state.state) == pytest.approx(expected)
        assert state.attributes["unit_of_measurement"] == "AUD/kWh"


async def test_unload_cancels_clock_callbacks_and_reload_retains_identity(hass, freezer, tariff_setup, entry):
    """Removing tariff entities cancels timers; reload installs one new listener."""
    now = datetime(2026, 11, 2, 10, 59, 59, tzinfo=ZoneInfo("Australia/Sydney"))
    freezer.move_to(now)
    await tariff_setup()
    key = "free_energy_window"
    binary_id = _entity_id(hass, key, "binary_sensor")
    old_entity = _entity(hass, key, "binary_sensor")
    with patch.object(old_entity, "async_write_ha_state", wraps=old_entity.async_write_ha_state) as old_write:
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        old_write.reset_mock()
        boundary = now.replace(hour=11, minute=0, second=0)
        freezer.move_to(boundary)
        async_fire_time_changed(hass, boundary)
        await hass.async_block_till_done()
        old_write.assert_not_called()
        # HA retains the registry's unavailable placeholder after unload.
        assert hass.states.get(binary_id).state == "unavailable"
        assert hass.states.get(binary_id).attributes["restored"] is True

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert _entity_id(hass, key, "binary_sensor") == binary_id
        assert hass.states.get(binary_id).state == "on"
        new_entity = _entity(hass, key, "binary_sensor")
        with patch.object(new_entity, "async_write_ha_state", wraps=new_entity.async_write_ha_state) as new_write:
            boundary = now.replace(hour=14, minute=0, second=0)
            freezer.move_to(boundary)
            async_fire_time_changed(hass, boundary)
            await hass.async_block_till_done()
            new_write.assert_called_once_with()
            old_write.assert_not_called()
            assert hass.states.get(binary_id).state == "off"
