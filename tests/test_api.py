"""API authentication and live-schema regression tests."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest

from custom_components.ovo_energy_au.api import (
    OVOEnergyAUApiClient,
    OVOEnergyAUApiClientAuthenticationError,
)
from custom_components.ovo_energy_au.graphql.queries import GET_BILLING_OVERVIEW


class _TokenResponse:
    def __init__(self, payload):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def raise_for_status(self):
        return None

    async def json(self):
        return self._payload


class _TokenSession:
    def __init__(self, claims):
        self.claims = claims

    def post(self, _url, json):
        return _TokenResponse(
            {
                "access_token": "access",
                "id_token": jwt.encode(self.claims, key="", algorithm="none"),
                "refresh_token": "refresh",
                "expires_in": 300,
            }
        )


@pytest.mark.asyncio
async def test_refresh_token_is_preferred_over_password_login():
    client = OVOEnergyAUApiClient(MagicMock(), "user@example.com", "password")
    now = datetime.now(UTC)
    client._access_token = "access"
    client._id_token = "id"
    client._refresh_token = "refresh"
    client._token_created_at = now - timedelta(minutes=4)
    client._token_expires_at = now + timedelta(seconds=10)
    client.refresh_tokens = AsyncMock(return_value={})
    client.authenticate_with_password = AsyncMock(return_value={})

    await client._ensure_authenticated()

    client.refresh_tokens.assert_awaited_once()
    client.authenticate_with_password.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejected_refresh_token_falls_back_to_password_login():
    client = OVOEnergyAUApiClient(MagicMock(), "user@example.com", "password")
    client._access_token = None
    client._refresh_token = "refresh"
    client.refresh_tokens = AsyncMock(
        side_effect=OVOEnergyAUApiClientAuthenticationError("expired")
    )
    client.authenticate_with_password = AsyncMock(return_value={})

    await client._ensure_authenticated()

    client.refresh_tokens.assert_awaited_once()
    client.authenticate_with_password.assert_awaited_once_with(
        "user@example.com", "password"
    )


@pytest.mark.asyncio
async def test_missing_auth0_nonce_is_accepted_after_state_and_pkce_validation():
    client = OVOEnergyAUApiClient(_TokenSession({}), "user@example.com", "password")

    tokens = await client._exchange_code_for_tokens(
        "code", "https://callback.example", "verifier", expected_nonce="expected"
    )

    assert tokens["access_token"] == "access"
    assert client.is_authenticated


@pytest.mark.asyncio
async def test_mismatched_auth0_nonce_remains_rejected():
    client = OVOEnergyAUApiClient(
        _TokenSession({"nonce": "wrong"}), "user@example.com", "password"
    )

    with pytest.raises(OVOEnergyAUApiClientAuthenticationError):
        await client._exchange_code_for_tokens(
            "code", "https://callback.example", "verifier", expected_nonce="expected"
        )


def test_billing_query_excludes_payment_method_identifiers():
    assert "directDebitDetails" in GET_BILLING_OVERVIEW
    assert "unbilledCharges" in GET_BILLING_OVERVIEW
    assert "paymentDetails" not in GET_BILLING_OVERVIEW
    assert "maskedCardNumber" not in GET_BILLING_OVERVIEW
    assert "maskedAccountNumber" not in GET_BILLING_OVERVIEW
