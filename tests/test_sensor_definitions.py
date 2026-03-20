"""Tests for sensor definitions integrity."""

import pytest
from unittest.mock import MagicMock

from custom_components.ovo_energy_au.sensors.definitions import (
    ANALYTICS_SENSORS,
    ENERGY_SENSORS,
    RATE_TYPE_ICONS,
    RATE_TYPES,
    calculate_free_savings,
    get_rate_value,
)


class TestSensorTupleStructure:
    """Verify every sensor definition tuple is well-formed."""

    def test_energy_sensors_all_have_8_fields(self):
        """Each ENERGY_SENSORS entry must be an 8-element tuple."""
        for i, sensor in enumerate(ENERGY_SENSORS):
            assert len(sensor) == 8, (
                f"ENERGY_SENSORS[{i}] (key={sensor[0]}) has {len(sensor)} elements, expected 8"
            )

    def test_analytics_sensors_all_have_8_fields(self):
        """Each ANALYTICS_SENSORS entry must be an 8-element tuple."""
        for i, sensor in enumerate(ANALYTICS_SENSORS):
            assert len(sensor) == 8, (
                f"ANALYTICS_SENSORS[{i}] (key={sensor[0]}) has {len(sensor)} elements, expected 8"
            )

    def test_all_sensor_keys_are_unique(self):
        """No duplicate keys across ENERGY + ANALYTICS sensors."""
        all_keys = [s[0] for s in ENERGY_SENSORS] + [s[0] for s in ANALYTICS_SENSORS]
        duplicates = [k for k in all_keys if all_keys.count(k) > 1]
        assert len(duplicates) == 0, f"Duplicate sensor keys: {set(duplicates)}"

    def test_all_value_fns_callable(self):
        """Every sensor's value_fn (index 6) must be callable."""
        for sensor in ENERGY_SENSORS + ANALYTICS_SENSORS:
            assert callable(sensor[6]), f"Sensor {sensor[0]!r} value_fn is not callable"

    def test_value_fns_handle_empty_data(self):
        """Calling each value_fn with {} must not raise."""
        for sensor in ENERGY_SENSORS + ANALYTICS_SENSORS:
            key, value_fn = sensor[0], sensor[6]
            try:
                value_fn({})
            except Exception as exc:
                pytest.fail(f"value_fn for {key!r} raised {type(exc).__name__}: {exc}")


class TestRateTypes:
    """Verify RATE_TYPES and RATE_TYPE_ICONS consistency."""

    def test_rate_types_have_icons(self):
        """Every entry in RATE_TYPES must have a matching entry in RATE_TYPE_ICONS."""
        for rt in RATE_TYPES:
            assert rt in RATE_TYPE_ICONS, f"RATE_TYPE {rt!r} missing from RATE_TYPE_ICONS"


class TestGetRateValue:
    """Test the get_rate_value helper."""

    def test_get_rate_value_with_valid_data(self):
        """Should extract the metric when available=True."""
        data = {
            "daily": {
                "rate_breakdown": {
                    "PEAK": {
                        "consumption": 5.0,
                        "charge": 1.75,
                        "available": True,
                    }
                }
            }
        }
        assert get_rate_value(data, "daily", "PEAK", "consumption") == 5.0
        assert get_rate_value(data, "daily", "PEAK", "charge") == 1.75

    def test_get_rate_value_with_missing_period(self):
        """Should return None when the period key doesn't exist."""
        data = {"daily": {"rate_breakdown": {}}}
        assert get_rate_value(data, "monthly", "PEAK", "consumption") is None

    def test_get_rate_value_with_missing_rate(self):
        """Should return None when the rate type doesn't exist."""
        data = {
            "daily": {
                "rate_breakdown": {
                    "PEAK": {"consumption": 5.0, "available": True}
                }
            }
        }
        assert get_rate_value(data, "daily", "OFFPEAK", "consumption") is None

    def test_get_rate_value_returns_none_when_not_available(self):
        """Should return None when available is False."""
        data = {
            "daily": {
                "rate_breakdown": {
                    "PEAK": {"consumption": 5.0, "available": False}
                }
            }
        }
        assert get_rate_value(data, "daily", "PEAK", "consumption") is None

    def test_get_rate_value_with_none_data(self):
        """Should return None when data is None."""
        assert get_rate_value(None, "daily", "PEAK", "consumption") is None

    def test_get_rate_value_with_empty_data(self):
        """Should return None when data is empty dict."""
        assert get_rate_value({}, "daily", "PEAK", "consumption") is None


class TestCalculateFreeSavings:
    """Test the calculate_free_savings helper."""

    def _make_coordinator(self, shoulder_rate: float = 0.25):
        coord = MagicMock()
        coord.plan_config = MagicMock()
        coord.plan_config.shoulder_rate = shoulder_rate
        return coord

    def test_calculate_free_savings_with_other_rate(self):
        """Should use OTHER rate to estimate free savings."""
        data = {
            "daily": {
                "rate_breakdown": {
                    "FREE_3": {
                        "consumption": 2.0,
                        "charge": 0.0,
                        "available": True,
                    },
                    "OTHER": {
                        "consumption": 10.0,
                        "charge": 3.50,
                        "available": True,
                    },
                }
            }
        }
        coord = self._make_coordinator()
        result = calculate_free_savings(data, "daily", coord)
        # free_consumption * (other_charge / other_consumption) = 2.0 * (3.50 / 10.0) = 0.70
        assert result == 0.70

    def test_calculate_free_savings_fallback_to_shoulder(self):
        """When OTHER is unavailable, should fall back to shoulder_rate."""
        data = {
            "daily": {
                "rate_breakdown": {
                    "FREE_3": {
                        "consumption": 4.0,
                        "charge": 0.0,
                        "available": True,
                    },
                    # No OTHER entry
                }
            }
        }
        coord = self._make_coordinator(shoulder_rate=0.30)
        result = calculate_free_savings(data, "daily", coord)
        # free_consumption * shoulder_rate = 4.0 * 0.30 = 1.20
        assert result == 1.20

    def test_calculate_free_savings_no_free_consumption(self):
        """Should return None when there is no FREE_3 data."""
        data = {
            "daily": {
                "rate_breakdown": {
                    "OTHER": {
                        "consumption": 10.0,
                        "charge": 3.50,
                        "available": True,
                    },
                }
            }
        }
        coord = self._make_coordinator()
        assert calculate_free_savings(data, "daily", coord) is None

    def test_calculate_free_savings_zero_other_consumption(self):
        """When OTHER consumption is zero, should fall back to shoulder rate."""
        data = {
            "daily": {
                "rate_breakdown": {
                    "FREE_3": {
                        "consumption": 3.0,
                        "charge": 0.0,
                        "available": True,
                    },
                    "OTHER": {
                        "consumption": 0.0,
                        "charge": 0.0,
                        "available": True,
                    },
                }
            }
        }
        coord = self._make_coordinator(shoulder_rate=0.25)
        result = calculate_free_savings(data, "daily", coord)
        # Falls back because other_consumption is 0 (falsy)
        assert result == 0.75  # 3.0 * 0.25
