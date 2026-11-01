"""Config options-flow regression tests."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.ovo_energy_au import config_flow as flow_module
from custom_components.ovo_energy_au.config_flow import ConfigFlow, OptionsFlowHandler
from custom_components.ovo_energy_au.const import (
    CONF_BILLING_CYCLE_DAY,
    CONF_CONSOLIDATE_DEVICES,
    CONF_EV_RATE,
    CONF_FLAT_RATE,
    CONF_OFF_PEAK_RATE,
    CONF_PEAK_END_HOUR,
    CONF_PEAK_RATE,
    CONF_PEAK_START_HOUR,
    CONF_PLAN_TYPE,
    CONF_SHOULDER_RATE,
    PLAN_BASIC,
    PLAN_EV,
    PLAN_FREE_4,
    PLAN_ONE,
)


@pytest.mark.asyncio
async def test_sign_in_does_not_inject_promotional_placeholders():
    flow = ConfigFlow()

    def show_form(**kwargs):
        return kwargs

    flow.async_show_form = show_form

    result = await flow.async_step_user()

    assert "description_placeholders" not in result


def test_config_dialogs_do_not_contain_promotions_or_referral_links():
    integration_dir = Path(__file__).parents[1] / "custom_components" / "ovo_energy_au"
    translation_files = [integration_dir / "strings.json"]
    translation_files.extend(sorted((integration_dir / "translations").glob("*.json")))
    forbidden = (
        "daniel16485",
        "starlink",
        "ovo_url",
        "ovo_friendly_url",
        "github_url",
        "referral code",
    )

    for translation_file in translation_files:
        data = json.loads(translation_file.read_text(encoding="utf-8"))
        dialog_text = json.dumps(
            {"config": data.get("config", {}), "options": data.get("options", {})},
            ensure_ascii=False,
        ).casefold()
        assert not any(term in dialog_text for term in forbidden), translation_file


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


@pytest.mark.asyncio
async def test_free_4_options_store_its_plan_and_peak_window():
    flow = OptionsFlowHandler()
    flow.config_entry = SimpleNamespace(data={}, options={}, runtime_data=None)

    result = await flow.async_step_init(
        {
            CONF_PLAN_TYPE: PLAN_FREE_4,
            CONF_BILLING_CYCLE_DAY: 1,
            CONF_PEAK_RATE: 0.4,
            CONF_SHOULDER_RATE: 0.3,
            CONF_OFF_PEAK_RATE: 0.2,
            CONF_PEAK_START_HOUR: 15,
            CONF_PEAK_END_HOUR: 21,
        }
    )

    assert result["data"][CONF_PLAN_TYPE] == PLAN_FREE_4
    assert result["data"][CONF_PEAK_START_HOUR] == 15
    assert result["data"][CONF_PEAK_END_HOUR] == 21


@pytest.mark.asyncio
async def test_options_stores_consolidate_devices():
    flow = OptionsFlowHandler()
    flow.config_entry = SimpleNamespace(data={}, options={})

    result = await flow.async_step_init(
        {
            CONF_PLAN_TYPE: PLAN_BASIC,
            CONF_BILLING_CYCLE_DAY: 1,
            CONF_CONSOLIDATE_DEVICES: True,
        }
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_CONSOLIDATE_DEVICES] is True


@pytest.mark.asyncio
async def test_successful_reauth_retires_persisted_legacy_tokens(monkeypatch):
    """Older releases stored tokens; reauth must not retain obsolete secrets."""
    monkeypatch.setattr(flow_module, "CONF_USERNAME", "username")
    monkeypatch.setattr(flow_module, "CONF_PASSWORD", "password")
    flow = ConfigFlow()
    flow._auth_data = {
        "username": "old@example.test",
        "password": "synthetic-old-password",  # pragma: allowlist secret
        "account_id": "account",
        "plan_type": PLAN_EV,
        **{key: f"legacy-{key}" for key in ("access_token", "id_token", "refresh_token")},
    }
    flow._reauth_entry = SimpleNamespace(unique_id="account", entry_id="entry")
    entries = SimpleNamespace(async_update_entry=MagicMock(), async_reload=AsyncMock())
    flow.hass = SimpleNamespace(config_entries=entries)
    flow.async_abort = lambda **kwargs: kwargs
    monkeypatch.setattr(flow_module, "validate_input", AsyncMock(return_value={"account_id": "account"}))

    result = await flow.async_step_reauth_confirm(
        {"username": "new@example.test", "password": "synthetic-new-password"}  # pragma: allowlist secret
    )

    assert result == {"reason": "reauth_successful"}
    saved_data = entries.async_update_entry.call_args.kwargs["data"]
    assert saved_data == {
        "username": "new@example.test",
        "password": "synthetic-new-password",  # pragma: allowlist secret
        "account_id": "account",
        "plan_type": PLAN_EV,
    }
    entries.async_reload.assert_awaited_once_with("entry")
