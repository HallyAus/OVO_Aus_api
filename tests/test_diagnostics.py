"""Diagnostics privacy regression tests."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.ovo_energy_au.diagnostics import (
    async_get_config_entry_diagnostics,
)


@pytest.mark.asyncio
async def test_diagnostics_redact_identity_and_omit_sensitive_payloads():
    coordinator = SimpleNamespace(
        data={
            "product_agreements": {
                "productAgreements": [
                    {
                        "nmi": "sensitive-meter-id",
                        "product": {"displayName": "The EV Plan"},
                    }
                ]
            },
            "statements": [{"downloadUrl": "https://signed.example"}],
            "payments": [{"amount": 10}],
            "hourly": {},
            "has_solar": True,
        },
        plan_config=SimpleNamespace(plan_type="ev"),
        last_update_success=True,
        last_update_success_time=None,
        hourly_data_status="stale",
        hourly_data_stale=True,
        hourly_last_success_time=datetime(2026, 3, 20, 1, 2, tzinfo=UTC),
        hourly_data_issue="empty_response",
    )
    entry = MagicMock()
    entry.runtime_data = coordinator
    entry.as_dict.return_value = {
        "title": "OVO (account)",
        "unique_id": "account",
        "data": {
            "username": "person@example.com",
            "password": "test-password",  # pragma: allowlist secret
            "account_id": "account",
        },
    }

    result = await async_get_config_entry_diagnostics(MagicMock(), entry)
    rendered = repr(result)

    assert "person@example.com" not in rendered
    assert "sensitive-meter-id" not in rendered
    assert "signed.example" not in rendered
    assert result["coordinator"]["statements_available"] == 1
    assert result["coordinator"]["payments_available"] == 1
    assert result["coordinator"]["hourly_data_status"] == "stale"
    assert result["coordinator"]["hourly_data_stale"] is True
    assert (
        result["coordinator"]["hourly_last_successful_update"]
        == "2026-03-20T01:02:00+00:00"
    )
    assert result["coordinator"]["hourly_data_issue"] == "empty_response"
