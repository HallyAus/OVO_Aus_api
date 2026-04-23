"""Shared fixtures for OVO Energy Australia tests."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

# Mock homeassistant module so imports don't fail outside HA
ha_mock = MagicMock()
sys.modules.setdefault("homeassistant", ha_mock)
sys.modules.setdefault("homeassistant.config_entries", ha_mock)
sys.modules.setdefault("homeassistant.const", ha_mock)
sys.modules.setdefault("homeassistant.core", ha_mock)
sys.modules.setdefault("homeassistant.exceptions", ha_mock)
sys.modules.setdefault("homeassistant.helpers", ha_mock)
sys.modules.setdefault("homeassistant.helpers.aiohttp_client", ha_mock)

# Build proper stub classes for sensor base classes so multiple inheritance
# in OVOBaseSensor(CoordinatorEntity, SensorEntity) doesn't hit a metaclass conflict.
class _CoordinatorEntity:
    """Stub for homeassistant.helpers.update_coordinator.CoordinatorEntity."""
    def __init__(self, *args, **kwargs):
        pass

class _SensorEntity:
    """Stub for homeassistant.components.sensor.SensorEntity."""
    pass

class _DataUpdateCoordinator:
    """Stub for DataUpdateCoordinator."""
    def __init__(self, *args, **kwargs):
        pass

class _TimestampDataUpdateCoordinator(_DataUpdateCoordinator):
    """Stub for TimestampDataUpdateCoordinator (adds last_update_success_time)."""
    last_update_success_time = None

class _UpdateFailed(Exception):
    """Stub for UpdateFailed."""
    pass

coordinator_mod = types.ModuleType("homeassistant.helpers.update_coordinator")
coordinator_mod.CoordinatorEntity = _CoordinatorEntity
coordinator_mod.DataUpdateCoordinator = _DataUpdateCoordinator
coordinator_mod.TimestampDataUpdateCoordinator = _TimestampDataUpdateCoordinator
coordinator_mod.UpdateFailed = _UpdateFailed
sys.modules.setdefault("homeassistant.helpers.update_coordinator", coordinator_mod)

sensor_mod = types.ModuleType("homeassistant.components.sensor")
sensor_mod.SensorEntity = _SensorEntity
sensor_mod.SensorDeviceClass = MagicMock()
sensor_mod.SensorStateClass = MagicMock()
sys.modules.setdefault("homeassistant.components.sensor", sensor_mod)

# Mock dt_util.now() to return a real datetime
from datetime import datetime as _dt, timezone as _tz
dt_mock = MagicMock()
dt_mock.now = MagicMock(return_value=_dt(2026, 3, 20, 12, 0, 0, tzinfo=_tz.utc))
util_mock = MagicMock()
util_mock.dt = dt_mock
sys.modules.setdefault("homeassistant.util", util_mock)
sys.modules.setdefault("homeassistant.util.dt", dt_mock)
sys.modules.setdefault("homeassistant.helpers.entity", ha_mock)
sys.modules.setdefault("homeassistant.helpers.entity_platform", ha_mock)
sys.modules.setdefault("homeassistant.data_entry_flow", ha_mock)
sys.modules.setdefault("aiohttp", ha_mock)
sys.modules.setdefault("jwt", ha_mock)
sys.modules.setdefault("voluptuous", ha_mock)

import pytest

from custom_components.ovo_energy_au.models import PlanConfig


@pytest.fixture
def plan_config() -> PlanConfig:
    """Default plan config for tests."""
    return PlanConfig(
        plan_type="ev",
        peak_rate=0.35,
        shoulder_rate=0.25,
        off_peak_rate=0.18,
        ev_rate=0.06,
        flat_rate=0.28,
    )


@pytest.fixture
def sample_interval_data() -> dict:
    """Sample interval data as returned by the OVO API."""
    return {
        "daily": {
            "solar": [
                {
                    "periodFrom": "2026-03-18T00:00:00Z",
                    "periodTo": "2026-03-19T00:00:00Z",
                    "consumption": 12.5,
                    "readType": "ACTUAL",
                    "charge": {"value": -1.25, "type": "CREDIT"},
                },
                {
                    "periodFrom": "2026-03-19T00:00:00Z",
                    "periodTo": "2026-03-20T00:00:00Z",
                    "consumption": 14.2,
                    "readType": "ACTUAL",
                    "charge": {"value": -1.42, "type": "CREDIT"},
                },
            ],
            "export": [
                {
                    "periodFrom": "2026-03-18T00:00:00Z",
                    "periodTo": "2026-03-19T00:00:00Z",
                    "consumption": 8.3,
                    "readType": "ACTUAL",
                    "charge": {"value": 2.49, "type": "DEBIT"},
                    "rates": [
                        {
                            "type": "EV_OFFPEAK",
                            "consumption": 3.0,
                            "charge": {"value": 0.18, "type": "DEBIT"},
                            "percentOfTotal": 0.36,
                        },
                        {
                            "type": "FREE_3",
                            "consumption": 2.0,
                            "charge": {"value": 0.0, "type": "DEBIT"},
                            "percentOfTotal": 0.24,
                        },
                        {
                            "type": "OTHER",
                            "consumption": 3.3,
                            "charge": {"value": 2.31, "type": "DEBIT"},
                            "percentOfTotal": 0.40,
                        },
                    ],
                },
                {
                    "periodFrom": "2026-03-19T00:00:00Z",
                    "periodTo": "2026-03-20T00:00:00Z",
                    "consumption": 9.1,
                    "readType": "ACTUAL",
                    "charge": {"value": 2.73, "type": "DEBIT"},
                    "rates": [
                        {
                            "type": "OTHER",
                            "consumption": 9.1,
                            "charge": {"value": 2.73, "type": "DEBIT"},
                            "percentOfTotal": 1.0,
                        },
                    ],
                },
            ],
        },
        "monthly": {
            "solar": [
                {
                    "periodFrom": "2026-03-01T00:00:00Z",
                    "periodTo": "2026-04-01T00:00:00Z",
                    "consumption": 280.0,
                    "charge": {"value": -28.0, "type": "CREDIT"},
                },
            ],
            "export": [
                {
                    "periodFrom": "2026-03-01T00:00:00Z",
                    "periodTo": "2026-04-01T00:00:00Z",
                    "consumption": 150.0,
                    "charge": {"value": 45.0, "type": "DEBIT"},
                    "rates": [
                        {
                            "type": "EV_OFFPEAK",
                            "consumption": 50.0,
                            "charge": {"value": 3.0, "type": "DEBIT"},
                            "percentOfTotal": 0.33,
                        },
                        {
                            "type": "FREE_3",
                            "consumption": 30.0,
                            "charge": {"value": 0.0, "type": "DEBIT"},
                            "percentOfTotal": 0.20,
                        },
                        {
                            "type": "OTHER",
                            "consumption": 70.0,
                            "charge": {"value": 42.0, "type": "DEBIT"},
                            "percentOfTotal": 0.47,
                        },
                    ],
                },
            ],
        },
        "yearly": {
            "solar": [
                {
                    "periodFrom": "2026-01-01T00:00:00Z",
                    "periodTo": "2027-01-01T00:00:00Z",
                    "consumption": 800.0,
                    "charge": {"value": -80.0, "type": "CREDIT"},
                },
            ],
            "export": [
                {
                    "periodFrom": "2026-01-01T00:00:00Z",
                    "periodTo": "2027-01-01T00:00:00Z",
                    "consumption": 500.0,
                    "charge": {"value": 150.0, "type": "DEBIT"},
                },
            ],
        },
    }


@pytest.fixture
def sample_hourly_data() -> dict:
    """Sample hourly data as returned by the OVO API."""
    entries = []
    for hour in range(24):
        entries.append({
            "periodFrom": f"2026-03-19T{hour:02d}:00:00Z",
            "periodTo": f"2026-03-19T{hour+1 if hour < 23 else 23}:59:00Z",
            "consumption": 0.5 + (0.3 if 7 <= hour <= 20 else 0),
            "readType": "ACTUAL",
            "charge": {"value": 0.15, "type": "DEBIT"},
            "rates": [
                {
                    "type": "EV_OFFPEAK" if hour < 6 else ("FREE_3" if 11 <= hour <= 13 else "OTHER"),
                    "consumption": 0.5 + (0.3 if 7 <= hour <= 20 else 0),
                    "charge": {
                        "value": 0.03 if hour < 6 else (0.0 if 11 <= hour <= 13 else 0.15),
                        "type": "DEBIT",
                    },
                    "percentOfTotal": 1.0,
                }
            ],
        })

    return {
        "solar": [
            {
                "periodFrom": f"2026-03-19T{hour:02d}:00:00Z",
                "periodTo": f"2026-03-19T{hour+1 if hour < 23 else 23}:59:00Z",
                "consumption": 0.8 if 8 <= hour <= 16 else 0,
                "charge": {"value": -0.08, "type": "CREDIT"},
            }
            for hour in range(24)
        ],
        "export": entries,
    }
