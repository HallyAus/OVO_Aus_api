"""API authentication and live-schema regression tests."""

import traceback
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlencode

import aiohttp
import jwt
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from custom_components.ovo_energy_au import api as api_module
from custom_components.ovo_energy_au.api import (
    OVOEnergyAUApiClient,
    OVOEnergyAUApiClientAuthenticationError,
    OVOEnergyAUApiClientCommunicationError,
)
from custom_components.ovo_energy_au.graphql.queries import GET_BILLING_OVERVIEW


class _TokenResponse:
    def __init__(self, payload, *, status=200, text="", url="https://example.test"):
        self._payload = payload
        self.status = status
        self._text = text
        self.url = url

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def raise_for_status(self):
        return None

    async def json(self):
        return self._payload

    async def text(self):
        return self._text


class _TokenSession:
    def __init__(self, claims):
        self.claims = claims

    def post(self, _url, json, **_kwargs):
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


async def _call_sensitive_endpoint(client, operation):
    if operation == "graphql":
        return await client._graphql_request("Result", "query Result { result }", {}, "Result")
    if operation == "login":
        return await client.authenticate_with_password("synthetic-user", "synthetic-password")
    if operation == "exchange":
        return await client._exchange_code_for_tokens("synthetic-code", "https://example.test", "synthetic-verifier")
    return await client.refresh_tokens()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["graphql", "login", "exchange", "refresh"])
@pytest.mark.parametrize("redirect_status", [302, 307, 308])
async def test_sensitive_endpoints_do_not_forward_secrets_to_redirects(
    monkeypatch, operation, redirect_status
):
    """Exercise real aiohttp redirects across origins with synthetic credentials."""
    received = []

    async def sink(request):
        received.append((request.method, dict(request.headers), await request.read()))
        return web.json_response(
            {
                "data": {"Result": {}},
                "access_token": "synthetic-new-access",
                "id_token": "synthetic-new-identity",
                "refresh_token": "synthetic-new-refresh",
                "expires_in": 300,
            }
        )

    sink_app = web.Application()
    sink_app.router.add_route("*", "/", sink)
    async with TestServer(sink_app) as sink_server:
        async def redirect(_request):
            return web.Response(
                status=redirect_status,
                headers={"Location": str(sink_server.make_url("/"))},
            )

        async def authorize(_request):
            return web.Response(status=200)

        origin_app = web.Application()
        origin_app.router.add_post("/sensitive", redirect)
        origin_app.router.add_get("/authorize", authorize)
        async with TestServer(origin_app) as origin_server:
            for name in ("GRAPHQL_URL", "OAUTH_LOGIN_URL", "OAUTH_TOKEN_URL"):
                monkeypatch.setattr(api_module, name, str(origin_server.make_url("/sensitive")))
            monkeypatch.setattr(api_module, "OAUTH_AUTHORIZE_URL", str(origin_server.make_url("/authorize")))
            async with aiohttp.ClientSession() as session:
                client = OVOEnergyAUApiClient(session)
                client.set_tokens("synthetic-access", "synthetic-identity", "synthetic-refresh", 3600)
                with pytest.raises(OVOEnergyAUApiClientCommunicationError, match="redirect"):
                    await _call_sensitive_endpoint(client, operation)

    assert received == []


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["graphql", "login", "exchange", "refresh"])
async def test_transport_errors_do_not_expose_provider_context(operation):
    session = MagicMock()
    private_context = "sensitive-provider-context"
    session.get.side_effect = aiohttp.ClientError(private_context)
    session.post.side_effect = aiohttp.ClientError(private_context)
    client = OVOEnergyAUApiClient(session)
    client.set_tokens("synthetic-access", "synthetic-identity", "synthetic-refresh", 3600)

    with pytest.raises(OVOEnergyAUApiClientCommunicationError) as captured:
        await _call_sensitive_endpoint(client, operation)

    assert private_context not in "".join(traceback.format_exception(captured.value))


@pytest.mark.asyncio
async def test_oauth_callback_error_does_not_echo_provider_description():
    private_context = "sensitive-oauth-provider-context"
    session = MagicMock()
    session.get.return_value = _TokenResponse({})
    form = '<form action="https://login.ovoenergy.com.au/login/callback"><input type="hidden" name="ticket" value="synthetic"></form>'
    session.post.side_effect = [
        _TokenResponse({}, text=form),
        _TokenResponse(
            {},
            url="https://my.ovoenergy.com.au?" + urlencode({"error": "access_denied", "error_description": private_context}),
        ),
    ]
    client = OVOEnergyAUApiClient(session)

    with pytest.raises(OVOEnergyAUApiClientAuthenticationError) as captured:
        await client.authenticate_with_password("synthetic-user", "synthetic-password")

    assert private_context not in "".join(traceback.format_exception(captured.value))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    [
        "http://login.ovoenergy.com.au/login/callback",
        "https://untrusted.example/login/callback",
        "https://login.ovoenergy.com.au.untrusted.example/login/callback",
        "https://user@login.ovoenergy.com.au/login/callback",
    ],
)
async def test_oauth_login_ticket_is_only_submitted_to_the_issuer(action):
    session = MagicMock()
    session.get.return_value = _TokenResponse({})
    form = f'<form action="{action}"><input type="hidden" name="ticket" value="synthetic"></form>'
    session.post.side_effect = [_TokenResponse({}, text=form), AssertionError("Untrusted form was submitted")]
    client = OVOEnergyAUApiClient(session)

    with pytest.raises(OVOEnergyAUApiClientAuthenticationError):
        await client.authenticate_with_password("synthetic-user", "synthetic-password")

    assert session.post.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("expires_in", ["invalid", float("inf"), 10**100, -1, 0, True])
async def test_invalid_refresh_lifetime_preserves_existing_tokens(expires_in):
    session = MagicMock()
    session.post.return_value = _TokenResponse(
        {
            "access_token": "synthetic-new-access",
            "id_token": "synthetic-new-identity",
            "refresh_token": "synthetic-new-refresh",
            "expires_in": expires_in,
        }
    )
    client = OVOEnergyAUApiClient(session)
    client.set_tokens("synthetic-access", "synthetic-identity", "synthetic-refresh", 3600)
    original = (client._access_token, client._id_token, client._refresh_token, client._token_created_at, client._token_expires_at)

    with pytest.raises(OVOEnergyAUApiClientCommunicationError):
        await client.refresh_tokens()

    assert (client._access_token, client._id_token, client._refresh_token, client._token_created_at, client._token_expires_at) == original
