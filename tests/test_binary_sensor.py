"""Tests for OVO Energy Australia binary sensor platform."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

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


@patch("custom_components.ovo_energy_au.binary_sensor.dt_util")
def test_free_energy_window_binary_sensor_free_3(mock_dt):
    """Test Free 3 plan window transitions."""
    coord = _create_mock_coordinator(plan_type="free_3")
    sensor = OVOFreeEnergyWindowBinarySensor(coord)

    # 10:00 - Outside free window (off)
    mock_dt.now.return_value = datetime(2026, 3, 20, 10, 0, tzinfo=AU_TIMEZONE)
    assert sensor.is_on is False
    assert sensor.icon == "mdi:clock-time-four-outline"
    assert sensor.extra_state_attributes["free_window"] == "11:00-14:00"

    # 11:00 - Inside free window (on)
    mock_dt.now.return_value = datetime(2026, 3, 20, 11, 0, tzinfo=AU_TIMEZONE)
    assert sensor.is_on is True
    assert sensor.icon == "mdi:gift"
    assert sensor.extra_state_attributes["hours_remaining"] == 3

    # 13:00 - Inside free window with 1 hour remaining
    mock_dt.now.return_value = datetime(2026, 3, 20, 13, 0, tzinfo=AU_TIMEZONE)
    assert sensor.is_on is True
    assert sensor.extra_state_attributes["hours_remaining"] == 1

    # 14:00 - Window ends (off)
    mock_dt.now.return_value = datetime(2026, 3, 20, 14, 0, tzinfo=AU_TIMEZONE)
    assert sensor.is_on is False
    assert sensor.icon == "mdi:clock-time-four-outline"


@patch("custom_components.ovo_energy_au.binary_sensor.dt_util")
def test_free_energy_window_binary_sensor_one_plan(mock_dt):
    """Test flat One Plan never activates free window."""
    coord = _create_mock_coordinator(plan_type="one", rates={"standard": 28})
    sensor = OVOFreeEnergyWindowBinarySensor(coord)

    mock_dt.now.return_value = datetime(2026, 3, 20, 12, 0, tzinfo=AU_TIMEZONE)
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
