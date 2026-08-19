"""Config options-flow regression tests."""

from types import SimpleNamespace

import pytest

from custom_components.ovo_energy_au.config_flow import ConfigFlow, OptionsFlowHandler
from custom_components.ovo_energy_au.const import (
    CONF_BILLING_CYCLE_DAY,
    CONF_EV_RATE,
    CONF_FLAT_RATE,
    CONF_OFF_PEAK_RATE,
    CONF_PEAK_RATE,
    CONF_PLAN_TYPE,
    CONF_SHOULDER_RATE,
    PLAN_EV,
    PLAN_ONE,
)


@pytest.mark.asyncio
async def test_sign_in_shows_direct_and_friendly_referral_urls():
    flow = ConfigFlow()

    def show_form(**kwargs):
        return kwargs

    flow.async_show_form = show_form

    result = await flow.async_step_user()

    placeholders = result["description_placeholders"]
    assert placeholders["ovo_url"] == (
        "https://www.ovoenergy.com.au/refer/daniel16485"
    )
    assert placeholders["ovo_friendly_url"] == "https://ovoreferralcode.com/"


@pytest.mark.asyncio
async def test_options_save_plan_settings_without_copying_credentials():
    flow = OptionsFlowHandler()
    flow.config_entry = SimpleNamespace(
        data={
            "username": "person@example.com",
            "password": "test-password",  # pragma: allowlist secret
        },
        options={},
    )

    result = await flow.async_step_init(
        {
            CONF_PLAN_TYPE: PLAN_EV,
            CONF_BILLING_CYCLE_DAY: 14,
            CONF_PEAK_RATE: 0.4,
            CONF_SHOULDER_RATE: 0.3,
            CONF_OFF_PEAK_RATE: 0.2,
            CONF_EV_RATE: 0.08,
            CONF_FLAT_RATE: 0.25,
        }
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_BILLING_CYCLE_DAY] == 14
    assert result["data"][CONF_EV_RATE] == 0.08
    assert "username" not in result["data"]
    assert "password" not in result["data"]
    assert CONF_FLAT_RATE not in result["data"]


@pytest.mark.asyncio
async def test_flat_plan_options_drop_time_of_use_rates():
    flow = OptionsFlowHandler()
    flow.config_entry = SimpleNamespace(data={}, options={})
    result = await flow.async_step_init(
        {
            CONF_PLAN_TYPE: PLAN_ONE,
            CONF_BILLING_CYCLE_DAY: 1,
            CONF_FLAT_RATE: 0.31,
        }
    )

    assert result["data"] == {
        CONF_PLAN_TYPE: PLAN_ONE,
        CONF_BILLING_CYCLE_DAY: 1,
        CONF_FLAT_RATE: 0.31,
    }
