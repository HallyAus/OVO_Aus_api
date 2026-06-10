"""Tests for PlanConfig data model."""

import pytest

from custom_components.ovo_energy_au.models import PlanConfig


class TestPlanConfig:
    """Test PlanConfig dataclass."""

    def test_default_values(self):
        """PlanConfig() with no args should use documented defaults."""
        pc = PlanConfig()
        assert pc.plan_type == "basic"
        assert pc.peak_rate == 0.35
        assert pc.shoulder_rate == 0.25
        assert pc.off_peak_rate == 0.18
        assert pc.ev_rate == 0.06
        assert pc.flat_rate == 0.28
        assert pc.peak_start_hour is None
        assert pc.peak_end_hour is None
        assert pc.has_other_split_window is False

    def test_from_dict_with_all_fields(self):
        """from_dict should populate every field from the dict."""
        d = {
            "plan_type": "ev",
            "peak_rate": 0.40,
            "shoulder_rate": 0.30,
            "off_peak_rate": 0.15,
            "ev_rate": 0.05,
            "flat_rate": 0.32,
        }
        pc = PlanConfig.from_dict(d)
        assert pc.plan_type == "ev"
        assert pc.peak_rate == 0.40
        assert pc.shoulder_rate == 0.30
        assert pc.off_peak_rate == 0.15
        assert pc.ev_rate == 0.05
        assert pc.flat_rate == 0.32

    def test_from_dict_with_partial_fields(self):
        """from_dict with only some keys should fall back to defaults for the rest."""
        d = {"plan_type": "tou", "peak_rate": 0.50}
        pc = PlanConfig.from_dict(d)
        assert pc.plan_type == "tou"
        assert pc.peak_rate == 0.50
        # defaults
        assert pc.shoulder_rate == 0.25
        assert pc.off_peak_rate == 0.18
        assert pc.ev_rate == 0.06
        assert pc.flat_rate == 0.28

    def test_from_dict_with_empty_dict(self):
        """from_dict({}) should produce identical results to PlanConfig()."""
        pc = PlanConfig.from_dict({})
        default = PlanConfig()
        assert pc.plan_type == default.plan_type
        assert pc.peak_rate == default.peak_rate
        assert pc.shoulder_rate == default.shoulder_rate
        assert pc.off_peak_rate == default.off_peak_rate
        assert pc.ev_rate == default.ev_rate
        assert pc.flat_rate == default.flat_rate

    def test_to_dict_roundtrip(self):
        """to_dict followed by from_dict should reproduce the same config."""
        original = PlanConfig(
            plan_type="ev",
            peak_rate=0.42,
            shoulder_rate=0.31,
            off_peak_rate=0.16,
            ev_rate=0.07,
            flat_rate=0.29,
        )
        d = original.to_dict()
        restored = PlanConfig.from_dict(d)

        assert restored.plan_type == original.plan_type
        assert restored.peak_rate == original.peak_rate
        assert restored.shoulder_rate == original.shoulder_rate
        assert restored.off_peak_rate == original.off_peak_rate
        assert restored.ev_rate == original.ev_rate
        assert restored.flat_rate == original.flat_rate

        # Also verify dict keys
        assert set(d.keys()) == {
            "plan_type", "peak_rate", "shoulder_rate",
            "off_peak_rate", "ev_rate", "flat_rate",
            "peak_start_hour", "peak_end_hour",
        }

    def test_peak_window_roundtrip(self):
        """peak_start_hour/peak_end_hour should survive to_dict/from_dict."""
        original = PlanConfig(plan_type="free_3", peak_start_hour=15, peak_end_hour=21)
        restored = PlanConfig.from_dict(original.to_dict())
        assert restored.peak_start_hour == 15
        assert restored.peak_end_hour == 21
        assert restored.has_other_split_window is True

    def test_has_other_split_window(self):
        """Window is valid only when both hours set and different."""
        assert PlanConfig(peak_start_hour=15, peak_end_hour=21).has_other_split_window
        # Overnight window is valid
        assert PlanConfig(peak_start_hour=21, peak_end_hour=7).has_other_split_window
        # start == end means disabled
        assert not PlanConfig(peak_start_hour=0, peak_end_hour=0).has_other_split_window
        # Partially configured means disabled
        assert not PlanConfig(peak_start_hour=15).has_other_split_window
        assert not PlanConfig(peak_end_hour=21).has_other_split_window
