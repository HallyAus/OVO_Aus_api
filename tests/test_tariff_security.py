"""Security regressions for the new public tariff entity surface."""

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.ovo_energy_au.binary_sensor import OVOFreeEnergyWindowBinarySensor
from custom_components.ovo_energy_au.const import AU_TIMEZONE
from custom_components.ovo_energy_au.models import PlanConfig
from custom_components.ovo_energy_au.sensor import (
    OVOElectricityPriceSensor,
    OVOSolarFeedInTariffSensor,
    OVOTariffPeriodSensor,
)
from custom_components.ovo_energy_au.tariff_entity import dt_util


def _coordinator(rates):
    # Canary strings are synthetic; no real OVO account or credentials are used.
    private = {
        key: f"private-fixture-{key}"
        for key in (
            "account_id", "nmi", "username", "password", "access_token",
            "refresh_token", "address", "vin", "latitude", "longitude",
        )
    }
    return SimpleNamespace(
        account_id=private["account_id"],
        plan_config=PlanConfig(plan_type="free_3"),
        last_update_success=True,
        auto_detect_plan=True,
        data={
            **private,
            "product_agreements": {
                "productAgreements": [{
                    **private,
                    "product": {
                        **private,
                        "displayName": "private-fixture-product-name",
                        "unitRatesCentsPerKWH": rates,
                    },
                }],
            },
        },
    )


@pytest.mark.parametrize("entity_class", [
    OVOFreeEnergyWindowBinarySensor, OVOElectricityPriceSensor,
    OVOSolarFeedInTariffSensor, OVOTariffPeriodSensor,
])
def test_tariff_attributes_never_expose_account_or_authentication_payloads(entity_class):
    coordinator = _coordinator({"peak": 25.74, "feedInTariff": 3.3})
    with patch.object(dt_util, "now", return_value=datetime(2026, 11, 2, 12, tzinfo=AU_TIMEZONE)):
        attributes = entity_class(coordinator).extra_state_attributes

    # Check values as well as keys: renaming an identifier must not bypass this.
    rendered = json.dumps(attributes, allow_nan=False)
    assert "private-fixture-" not in rendered
    assert all(value is None or isinstance(value, (str, int, float)) for value in attributes.values())


@pytest.mark.parametrize("untrusted_rate", [
    True, False, float("nan"), float("inf"), float("-inf"),
    "NaN", "Infinity", {"access_token": "private-fixture-token"},
    ["private-fixture-token"], "<script>private-fixture-token</script>",
])
def test_untrusted_rate_values_cannot_reach_numeric_tariff_states(untrusted_rate):
    coordinator = _coordinator({"peak": untrusted_rate, "feedInTariff": untrusted_rate})
    with patch.object(dt_util, "now", return_value=datetime(2026, 11, 2, 10, tzinfo=AU_TIMEZONE)):
        price = OVOElectricityPriceSensor(coordinator)
        feed_in = OVOSolarFeedInTariffSensor(coordinator)
        assert price.native_value == 0.35  # Validated manual fallback, never raw data.
        assert feed_in.native_value is None
        public = json.dumps(
            [price.extra_state_attributes, feed_in.extra_state_attributes], allow_nan=False
        )
    assert "private-fixture-" not in public


@pytest.mark.parametrize("plan_type", ["free_3", "free_4"])
def test_binary_window_does_not_trust_unrelated_api_price_fields(plan_type):
    coordinator = _coordinator({"standard": 0, "superOffPeak": 0})
    coordinator.plan_config.plan_type = plan_type
    with patch.object(dt_util, "now", return_value=datetime(2026, 11, 2, 23, tzinfo=AU_TIMEZONE)):
        assert OVOFreeEnergyWindowBinarySensor(coordinator).is_on is False
