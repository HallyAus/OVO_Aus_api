"""Tests for OVO Energy Australia binary sensor platform."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.ovo_energy_au.binary_sensor import (
    OVOFreeEnergyWindowBinarySensor,
    async_setup_entry,
)
from custom_components.ovo_energy_au.const import AU_TIMEZONE, DOMAIN
from custom_components.ovo_energy_au.models import PlanConfig


def _create_mock_coordinator(plan_type="free_3", rates=None):
    coordinator = MagicMock()
    coordinator.account_id = "12345"
    coordinator.last_update_success = True
    coordinator.auto_detect_plan = False
    coordinator.plan_config = PlanConfig(plan_type=plan_type)
    coordinator.data = {
        "product_agreements": {
            "productAgreements": [
                {
                    "status": "ACTIVE",
                    "product": {
                        "displayName": f"The {plan_type.replace('_', ' ').title()} Plan",
                        "unitRatesCentsPerKWH": rates or {"peak": 35, "superOffPeak": 0},
                    },
                }
            ]
        }
    }
    return coordinator


@patch.object(dt_util, "now")
def test_free_energy_window_binary_sensor_free_3(mock_now):
    """Test Free 3 plan window transitions."""
    coord = _create_mock_coordinator(plan_type="free_3")
    sensor = OVOFreeEnergyWindowBinarySensor(coord)

    # 10:00 - Outside free window (off)
    mock_now.return_value = datetime(2026, 3, 20, 10, 0, tzinfo=AU_TIMEZONE)
    assert sensor.is_on is False
    assert sensor.icon == "mdi:clock-time-four-outline"
    assert sensor.extra_state_attributes["free_window"] == "11:00-14:00"

    # 11:00 - Inside free window (on)
    mock_now.return_value = datetime(2026, 3, 20, 11, 0, tzinfo=AU_TIMEZONE)
    assert sensor.is_on is True
    assert sensor.icon == "mdi:gift"
    assert sensor.extra_state_attributes["hours_remaining"] == 3

    # 13:00 - Inside free window with 1 hour remaining
    mock_now.return_value = datetime(2026, 3, 20, 13, 0, tzinfo=AU_TIMEZONE)
    assert sensor.is_on is True
    assert sensor.extra_state_attributes["hours_remaining"] == 1

    # 14:00 - Window ends (off)
    mock_now.return_value = datetime(2026, 3, 20, 14, 0, tzinfo=AU_TIMEZONE)
    assert sensor.is_on is False
    assert sensor.icon == "mdi:clock-time-four-outline"


@patch.object(dt_util, "now")
def test_free_energy_window_binary_sensor_one_plan(mock_now):
    """Test flat One Plan never activates free window."""
    coord = _create_mock_coordinator(plan_type="one", rates={"standard": 28})
    sensor = OVOFreeEnergyWindowBinarySensor(coord)

    mock_now.return_value = datetime(2026, 3, 20, 12, 0, tzinfo=AU_TIMEZONE)
    assert sensor.is_on is False
    assert sensor.icon == "mdi:clock-time-four-outline"


def test_free_energy_window_device_info():
    """Verify binary sensor points to primary account device."""
    coord = _create_mock_coordinator()
    sensor = OVOFreeEnergyWindowBinarySensor(coord)
    assert sensor.device_info["identifiers"] == {(DOMAIN, "12345")}
    assert sensor.device_info["name"] == "OVO Energy AU"


@pytest.mark.asyncio
async def test_async_setup_entry_binary_sensor():
    """Test binary sensor async_setup_entry adds entity."""
    coord = _create_mock_coordinator()
    entry = MagicMock()
    entry.runtime_data = coord
    entities = []

    await async_setup_entry(MagicMock(), entry, entities.extend)
    assert len(entities) == 1
    assert isinstance(entities[0], OVOFreeEnergyWindowBinarySensor)


@pytest.mark.parametrize(
    ("plan_type", "hour", "minute", "second", "expected"),
    [
        ("free_3", 10, 59, 59, False),
        ("free_3", 11, 0, 0, True),
        ("free_3", 11, 0, 1, True),
        ("free_3", 13, 59, 59, True),
        ("free_3", 14, 0, 0, False),
        ("free_3", 14, 0, 1, False),
        ("free_4", 10, 59, 59, False),
        ("free_4", 11, 0, 0, True),
        ("free_4", 11, 0, 1, True),
        ("free_4", 14, 0, 0, True),
        ("free_4", 14, 59, 59, True),
        ("free_4", 15, 0, 0, False),
        ("free_4", 15, 0, 1, False),
    ],
)
def test_free_window_boundaries_are_start_inclusive_end_exclusive(
    plan_type, hour, minute, second, expected
):
    """Both advertised windows include their start and exclude their end."""
    sensor = OVOFreeEnergyWindowBinarySensor(_create_mock_coordinator(plan_type))
    now = datetime(2026, 11, 2, hour, minute, second, tzinfo=AU_TIMEZONE)
    with patch.object(dt_util, "now", return_value=now):
        assert sensor.is_on is expected
        assert ("hours_remaining" in sensor.extra_state_attributes) is expected


@pytest.mark.parametrize(("plan_type", "end_hour"), [("free_3", 14), ("free_4", 15)])
@pytest.mark.parametrize("rate_key", ["standard", "peak"])
@pytest.mark.parametrize("after_window", [False, True])
def test_zero_ordinary_price_does_not_activate_free_window(plan_type, end_hour, rate_key, after_window):
    """A zero ordinary tariff does not extend the plan's dedicated free window."""
    sensor = OVOFreeEnergyWindowBinarySensor(
        _create_mock_coordinator(plan_type, {rate_key: 0})
    )
    hour = end_hour if after_window else 10
    with patch.object(
        dt_util, "now", return_value=datetime(2026, 11, 2, hour, tzinfo=AU_TIMEZONE)
    ):
        assert sensor.is_on is False
        assert sensor.icon == "mdi:clock-time-four-outline"
        assert "hours_remaining" not in sensor.extra_state_attributes


@pytest.mark.parametrize(
    ("super_rate", "hour", "expected"),
    [(0, 10, False), (0, 11, True), (0, 13, True), (0, 14, False),
     (0, 1, False), (6, 12, False), (None, 12, False)],
)
def test_ev_free_window_requires_a_free_super_off_peak_rate(super_rate, hour, expected):
    """EV overnight and paid super-off-peak periods are not the free window."""
    rates = {"peak": 35, "evOffPeak": 0}
    if super_rate is not None:
        rates["superOffPeak"] = super_rate
    sensor = OVOFreeEnergyWindowBinarySensor(_create_mock_coordinator("ev", rates))
    with patch.object(
        dt_util, "now", return_value=datetime(2026, 11, 2, hour, tzinfo=AU_TIMEZONE)
    ):
        assert sensor.is_on is expected


@pytest.mark.parametrize("has_product", [False, True])
@pytest.mark.parametrize("last_update_success", [False, True])
def test_auto_detected_window_requires_current_product_and_successful_coordinator(
    has_product, last_update_success
):
    """An unknown tariff or failed update must not publish a healthy state."""
    coordinator = _create_mock_coordinator()
    coordinator.auto_detect_plan = True
    coordinator.last_update_success = last_update_success
    if not has_product:
        coordinator.data = {"product_agreements": {"productAgreements": []}}
    sensor = OVOFreeEnergyWindowBinarySensor(coordinator)
    assert sensor.available is (has_product and last_update_success)


@pytest.mark.parametrize("last_update_success", [False, True])
def test_manual_plan_can_supply_window_without_api_product(last_update_success):
    """An explicitly configured plan needs a healthy coordinator, not an API product."""
    coordinator = _create_mock_coordinator()
    coordinator.last_update_success = last_update_success
    coordinator.data = {}
    sensor = OVOFreeEnergyWindowBinarySensor(coordinator)
    assert sensor.available is last_update_success


@pytest.mark.parametrize(
    ("plan_type", "hour", "minute", "second", "expected"),
    [("free_3", 12, 30, 0, 1.5), ("free_3", 13, 59, 0, 1 / 60),
     ("free_3", 13, 59, 59, 1 / 3600), ("free_4", 12, 30, 0, 2.5),
     ("free_4", 14, 59, 0, 1 / 60), ("free_4", 14, 59, 59, 1 / 3600)],
)
def test_hours_remaining_accounts_for_minutes_and_seconds(plan_type, hour, minute, second, expected):
    """The countdown must not report an hour when only seconds remain."""
    sensor = OVOFreeEnergyWindowBinarySensor(_create_mock_coordinator(plan_type))
    now = datetime(2026, 11, 2, hour, minute, second, tzinfo=AU_TIMEZONE)
    with patch.object(dt_util, "now", return_value=now):
        assert sensor.extra_state_attributes["hours_remaining"] == pytest.approx(expected, abs=0.0001)
