"""Tests for sensor definitions integrity."""

from unittest.mock import MagicMock

import pytest

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


class TestTimeOfUseSensors:
    """Verify the TOU peak/off-peak split sensors (#74) actually surface data.

    Regression guard: v4.2.0 computed `hourly.time_of_use` (and re-bucketed
    OTHER into peak/off-peak for Free 3) but exposed no sensor reading it, so
    the values never reached Home Assistant. These assert the value_fns read
    the correct path through a realistic coordinator.data dict.
    """

    TOU_KEYS = {
        "tou_peak_consumption",
        "tou_off_peak_consumption",
    }

    def _value_fn(self, key):
        for sensor in ANALYTICS_SENSORS:
            if sensor[0] == key:
                return sensor[6]
        raise AssertionError(f"sensor {key!r} not found in ANALYTICS_SENSORS")

    def test_tou_sensors_exist(self):
        """Both TOU split consumption sensors must be defined. (Cost sensors are
        intentionally absent: the hourly API has no per-hour cost data.)"""
        defined = {s[0] for s in ANALYTICS_SENSORS}
        missing = self.TOU_KEYS - defined
        assert not missing, f"TOU sensors missing from ANALYTICS_SENSORS: {missing}"
        # Cost sensors must NOT exist (would always read 0).
        assert "tou_peak_cost" not in defined
        assert "tou_off_peak_cost" not in defined

    def test_tou_value_fns_read_real_data(self):
        """value_fns must extract peak/off_peak consumption from the
        coordinator.data[hourly][time_of_use] structure produced by
        analytics.hourly._compute_tou_breakdown / _split_other_by_window."""
        data = {
            "hourly": {
                "time_of_use": {
                    "peak": {"consumption": 3.5, "cost": 0.0, "hours": 4},
                    "off_peak": {"consumption": 1.5, "cost": 0.0, "hours": 3},
                    "other": {"consumption": 0.0, "cost": 0.0, "hours": 0},
                }
            }
        }
        assert self._value_fn("tou_peak_consumption")(data) == 3.5
        assert self._value_fn("tou_off_peak_consumption")(data) == 1.5

    def test_tou_value_fns_handle_missing_hourly(self):
        """No hourly/time_of_use data yet → None, never an exception."""
        for key in self.TOU_KEYS:
            assert self._value_fn(key)({}) is None
            assert self._value_fn(key)({"hourly": {}}) is None


class TestBillAndTariffSensors:
    """Real-bill (statements) and API-rate sensors (#74 follow-ups)."""

    def _vfn(self, key):
        for s in ANALYTICS_SENSORS:
            if s[0] == key:
                return s[6]
        raise AssertionError(f"{key!r} not in ANALYTICS_SENSORS")

    def test_latest_bill_value_fns(self):
        data = {"latest_bill": {"total": 78.5, "closing_balance": 24.5, "opening_balance": 55.05}}
        assert self._vfn("latest_bill_amount")(data) == 78.5
        assert self._vfn("latest_bill_closing_balance")(data) == 24.5
        assert self._vfn("latest_bill_opening_balance")(data) == 55.05

    def test_latest_bill_empty_safe(self):
        for key in ("latest_bill_amount", "latest_bill_closing_balance",
                    "latest_bill_opening_balance"):
            assert self._vfn(key)({}) is None

    def test_tariff_rate_value_fns_convert_cents_to_dollars(self):
        data = {"product_agreements": {"productAgreements": [
            {"product": {"unitRatesCentsPerKWH": {"peak": 37.18, "shoulder": 25.0,
                                                  "offPeak": 18.0, "evOffPeak": 8.0,
                                                  "feedInTariff": 3.3},
                         "standingChargeCentsPerDay": 110.0}}]}}
        assert self._vfn("tariff_peak_rate")(data) == 0.3718
        assert self._vfn("tariff_shoulder_rate")(data) == 0.25
        assert self._vfn("tariff_off_peak_rate")(data) == 0.18
        assert self._vfn("tariff_ev_off_peak_rate")(data) == 0.08
        assert self._vfn("tariff_feed_in_rate")(data) == 0.033
        assert self._vfn("tariff_standing_charge")(data) == 1.10

    def test_tariff_rate_empty_safe(self):
        for key in ("tariff_peak_rate", "tariff_shoulder_rate", "tariff_off_peak_rate",
                    "tariff_ev_off_peak_rate", "tariff_feed_in_rate", "tariff_standing_charge"):
            assert self._vfn(key)({}) is None
            assert self._vfn(key)({"product_agreements": None}) is None


class TestEnergyDashboardSensor:
    """Energy Dashboard cumulative sensors (#73)."""

    def _coord(self, data):
        c = MagicMock()
        c.account_id = "123"
        c.data = data
        return c

    def test_reads_monthly_total_and_resets_monthly(self):
        from custom_components.ovo_energy_au.sensor import OVOEnergyDashboardSensor
        c = self._coord({"monthly": {"grid_consumption": 841.31, "return_to_grid": 12.0,
                                     "solar_consumption": 92.36}})
        s = OVOEnergyDashboardSensor(c, "energy_grid_import", "Grid Import",
                                     "grid_consumption", "mdi:transmission-tower-import")
        assert s.native_value == 841.31
        # last_reset is the first of the current month (so HA handles the monthly reset)
        assert s.last_reset.day == 1
        assert s.last_reset.hour == 0

    def test_none_when_no_data(self):
        from custom_components.ovo_energy_au.sensor import OVOEnergyDashboardSensor
        s = OVOEnergyDashboardSensor(self._coord(None), "energy_grid_import", "Grid Import",
                                     "grid_consumption", "mdi:transmission-tower-import")
        assert s.native_value is None

    def test_export_and_solar_keys(self):
        from custom_components.ovo_energy_au.sensor import OVOEnergyDashboardSensor
        c = self._coord({"monthly": {"return_to_grid": 12.0, "solar_consumption": 92.36}})
        exp = OVOEnergyDashboardSensor(c, "energy_grid_export", "Grid Export",
                                       "return_to_grid", "mdi:x")
        sol = OVOEnergyDashboardSensor(c, "energy_solar_production", "Solar",
                                       "solar_consumption", "mdi:x")
        assert exp.native_value == 12.0
        assert sol.native_value == 92.36


class TestPaymentAndReferralSensors:
    """Payments + refer-a-friend sensors (verified against live data)."""

    def _coord(self, data):
        c = MagicMock()
        c.account_id = "123"
        c.data = data
        return c

    def test_latest_payment(self):
        from custom_components.ovo_energy_au.sensor import OVOLatestPaymentSensor
        c = self._coord({
            "latest_payment": {"amount": 120, "date": "2026-05-14", "type": "DIRECT_DEBIT"},
            "payments": [{"amount": 120, "date": "2026-05-14", "type": "DIRECT_DEBIT"}],
        })
        s = OVOLatestPaymentSensor(c)
        assert s.native_value == 120.0
        attrs = s.extra_state_attributes
        assert attrs["date"] == "2026-05-14"
        assert attrs["payment_type"] == "DIRECT_DEBIT"
        assert attrs["payment_count"] == 1

    def test_referral(self):
        from custom_components.ovo_energy_au.sensor import OVOReferralSensor
        c = self._coord({"referral": {"code": "daniel16485", "total_earned": 45.03,
                                      "referral_count": 2}})
        s = OVOReferralSensor(c)
        assert s.native_value == 45.03
        assert s.extra_state_attributes["referral_code"] == "daniel16485"
        assert s.extra_state_attributes["referrals"] == 2

    def test_empty_safe(self):
        from custom_components.ovo_energy_au.sensor import OVOLatestPaymentSensor, OVOReferralSensor
        assert OVOLatestPaymentSensor(self._coord(None)).native_value is None
        assert OVOReferralSensor(self._coord({})).native_value is None

    def test_flex_onboarded(self):
        from custom_components.ovo_energy_au.sensor import OVOFlexSensor
        assert OVOFlexSensor(self._coord({"flex": {"onboarded": True}})).native_value == "Onboarded"
        assert OVOFlexSensor(self._coord({"flex": {"onboarded": False}})).native_value == "Not Onboarded"
        # No flex data yet -> None (unknown), never a crash
        assert OVOFlexSensor(self._coord({"flex": {}})).native_value is None
        assert OVOFlexSensor(self._coord(None)).native_value is None


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
