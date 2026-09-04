"""Plan detection and current-tariff regression tests."""

import pytest

from custom_components.ovo_energy_au.const import (
    PLAN_EV,
    PLAN_FREE_3,
    PLAN_FREE_4,
    PLAN_ONE,
)
from custom_components.ovo_energy_au.models import PlanConfig
from custom_components.ovo_energy_au.tariffs import (
    detect_plan_type,
    get_current_product,
    get_tariff_details,
    update_plan_config_rates,
)


def _data(rates: dict) -> dict:
    return {"product_agreements": {"productAgreements": [{"product": {"unitRatesCentsPerKWH": rates}}]}}


def test_detects_current_and_basic_plan_names():
    assert detect_plan_type("The Free 4 Plan") == PLAN_FREE_4
    assert detect_plan_type("The Basic Free4 Plan (TOU)") == PLAN_FREE_4
    assert detect_plan_type("The Free 3 Plan") == PLAN_FREE_3
    assert detect_plan_type("The Basic EV Plan") == PLAN_EV
    assert detect_plan_type("The One Plan (TOU)") == PLAN_ONE
    assert detect_plan_type("Unrecognised legacy product") is None


def test_free_4_uses_the_full_11_to_15_window():
    config = PlanConfig(plan_type=PLAN_FREE_4)
    data = _data({"peak": 39.765, "superOffPeak": 0})

    details = get_tariff_details(config, data, 14)

    assert details["current_period"] == "Super Off-Peak (FREE)"
    assert details["rate_cents_kwh"] == 0
    assert details["next_period_change"] == "15:00"
    assert details["free_window"] == "11:00-15:00"
    assert get_tariff_details(config, data, 15)["current_period"] == "Standard"


def test_free_period_never_uses_a_nonzero_placeholder_rate():
    config = PlanConfig(plan_type=PLAN_FREE_4)
    data = _data({"peak": 39.765, "superOffPeak": 12.1})

    details = get_tariff_details(config, data, 14)

    assert details["current_period"] == "Super Off-Peak (FREE)"
    assert details["rate_cents_kwh"] == 0
    assert details["rate_aud_kwh"] == 0


def test_free_3_uses_configured_peak_and_off_peak_rates():
    config = PlanConfig(
        plan_type=PLAN_FREE_3,
        peak_rate=0.42,
        off_peak_rate=0.21,
        peak_start_hour=15,
        peak_end_hour=21,
    )
    data = _data({"peak": 42, "offPeak": 21, "superOffPeak": 0})

    assert get_tariff_details(config, data, 12)["current_period"] == ("Super Off-Peak (FREE)")
    peak = get_tariff_details(config, data, 16)
    assert peak["current_period"] == "Peak"
    assert peak["rate_cents_kwh"] == 42
    off_peak = get_tariff_details(config, data, 22)
    assert off_peak["current_period"] == "Off-Peak"
    assert off_peak["rate_cents_kwh"] == 21


def test_one_plan_nonzero_super_off_peak_is_not_labelled_free_or_ev():
    config = PlanConfig(plan_type=PLAN_ONE)
    data = _data({"peak": 23.98, "superOffPeak": 12.1})

    details = get_tariff_details(config, data, 12)

    assert details["current_period"] == "Super Off-Peak"
    assert details["rate_cents_kwh"] == 12.1
    assert details["next_period_change"] == "16:00"
    assert details["super_off_peak_window"] == "11:00-16:00"
    assert get_tariff_details(config, data, 1)["current_period"] == "Standard"


def test_one_plan_full_reported_tou_schedule_with_configured_peak_window():
    config = PlanConfig(
        plan_type=PLAN_ONE,
        peak_start_hour=16,
        peak_end_hour=21,
    )
    data = _data({"peak": 23.98, "offPeak": 18.5, "superOffPeak": 12.1})

    expected = ["Off-Peak"] * 11 + ["Super Off-Peak"] * 5 + ["Peak"] * 5 + ["Off-Peak"] * 3
    actual = [get_tariff_details(config, data, hour)["current_period"] for hour in range(24)]

    assert actual == expected


def test_paid_super_off_peak_ends_at_the_configured_peak_boundary():
    config = PlanConfig(
        plan_type=PLAN_ONE,
        peak_start_hour=15,
        peak_end_hour=21,
    )
    data = _data({"peak": 40, "offPeak": 20, "superOffPeak": 10})

    assert get_tariff_details(config, data, 14)["current_period"] == ("Super Off-Peak")
    at_peak = get_tariff_details(config, data, 15)
    assert at_peak["current_period"] == "Peak"
    assert at_peak["super_off_peak_window"] == "11:00-15:00"


def test_latest_active_product_wins_when_completed_agreement_is_first():
    data = {
        "product_agreements": {
            "productAgreements": [
                {
                    "fromDt": "2024-01-01",
                    "toDt": "2024-12-31",
                    "product": {"displayName": "The One Plan"},
                },
                {
                    "fromDt": "2025-01-01",
                    "toDt": None,
                    "product": {"displayName": "The Free 4 Plan"},
                },
            ]
        }
    }

    assert get_current_product(data)["displayName"] == "The Free 4 Plan"
    assert get_current_product(data["product_agreements"])["displayName"] == ("The Free 4 Plan")


def test_live_product_rates_refresh_automatic_fallbacks():
    config = PlanConfig(
        plan_type=PLAN_ONE,
        peak_rate=0.99,
        shoulder_rate=0.99,
        off_peak_rate=0.99,
        ev_rate=0.99,
        flat_rate=0.99,
    )
    data = _data(
        {
            "peak": 42.1,
            "shoulder": 31.2,
            "offPeak": 20.3,
            "evOffPeak": 4.5,
            "standard": 28.4,
        }
    )

    update_plan_config_rates(config, data)

    assert config.peak_rate == pytest.approx(0.421)
    assert config.shoulder_rate == pytest.approx(0.312)
    assert config.off_peak_rate == pytest.approx(0.203)
    assert config.ev_rate == pytest.approx(0.045)
    assert config.flat_rate == pytest.approx(0.284)


def test_current_ev_plan_uses_nonzero_midday_super_off_peak_rate():
    config = PlanConfig(plan_type=PLAN_EV)
    data = _data({"peak": 60.192, "evOffPeak": 4.5, "superOffPeak": 19.02})

    assert get_tariff_details(config, data, 1)["current_period"] == "EV Off-Peak"
    midday = get_tariff_details(config, data, 12)
    assert midday["current_period"] == "Super Off-Peak"
    assert midday["rate_cents_kwh"] == 19.02
