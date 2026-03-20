"""API client for OVO Energy Australia."""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import html
import logging
import re
import secrets
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import aiohttp
import jwt

from .const import (
    API_BASE_URL,
    AUTH_BASE_URL,
    GRAPHQL_URL,
    MIN_REQUEST_INTERVAL_SECONDS,
    OAUTH_AUDIENCE,
    OAUTH_AUTHORIZE_URL,
    OAUTH_CLIENT_ID,
    OAUTH_CONNECTION,
    OAUTH_LOGIN_URL,
    OAUTH_REDIRECT_URI,
    OAUTH_SCOPES,
    OAUTH_TOKEN_URL,
    TOKEN_REFRESH_BUFFER_PERCENT,
    TOKEN_REFRESH_MAX_BUFFER_SECONDS,
    TOKEN_REFRESH_MIN_BUFFER_SECONDS,
)
from .graphql.queries import (
    GET_CONTACT_INFO,
    GET_HOURLY_DATA,
    GET_INTERVAL_DATA,
    GET_PRODUCT_AGREEMENTS,
)

_LOGGER = logging.getLogger(__name__)


class OVOEnergyAUApiClientError(Exception):
    """General API error."""


class OVOEnergyAUApiClientAuthenticationError(OVOEnergyAUApiClientError):
    """Authentication error."""


class OVOEnergyAUApiClientCommunicationError(OVOEnergyAUApiClientError):
    """Communication error."""


class OVOEnergyAUApiClient:
    """API client for OVO Energy Australia."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._username = username
        self._password = password
        self._access_token: str | None = None
        self._id_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._token_created_at: datetime | None = None
        self._refresh_lock = asyncio.Lock()
        self._last_request_time: float | None = None
        self._rate_limit_lock = asyncio.Lock()

    # ─── Token management ────────────────────────────────────────────

    @property
    def is_authenticated(self) -> bool:
        """Return True if the client has a valid token."""
        return self._access_token is not None and not self.token_expired

    @property
    def token_expired(self) -> bool:
        """Return True if the token has actually expired (no buffer)."""
        if self._token_expires_at is None:
            return True
        return datetime.now(timezone.utc) >= self._token_expires_at

    @property
    def should_refresh(self) -> bool:
        """Return True if the token should be proactively refreshed."""
        if self._token_expires_at is None:
            return True

        now = datetime.now(timezone.utc)
        if self._token_created_at:
            token_lifetime = (self._token_expires_at - self._token_created_at).total_seconds()
            buffer_seconds = max(
                TOKEN_REFRESH_MIN_BUFFER_SECONDS,
                min(
                    token_lifetime * TOKEN_REFRESH_BUFFER_PERCENT,
                    TOKEN_REFRESH_MAX_BUFFER_SECONDS,
                ),
            )
        else:
            buffer_seconds = TOKEN_REFRESH_MIN_BUFFER_SECONDS

        return now >= (self._token_expires_at - timedelta(seconds=buffer_seconds))

    def set_tokens(
        self,
        access_token: str,
        id_token: str,
        refresh_token: str | None = None,
        expires_in: int | None = None,
    ) -> None:
        """Set authentication tokens."""
        self._access_token = access_token
        self._id_token = id_token
        self._refresh_token = refresh_token
        self._token_created_at = datetime.now(timezone.utc)

        if expires_in is not None:
            self._token_expires_at = self._token_created_at + timedelta(seconds=expires_in)
        else:
            try:
                decoded = jwt.decode(access_token, options={"verify_signature": False})
                exp_timestamp = decoded.get("exp")
                if exp_timestamp:
                    self._token_expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
                else:
                    self._token_expires_at = self._token_created_at + timedelta(hours=1)
            except Exception:
                self._token_expires_at = self._token_created_at + timedelta(hours=1)

        token_lifetime = (self._token_expires_at - self._token_created_at).total_seconds()
        _LOGGER.info(
            "Tokens set. Lifetime: %d seconds (%.1f hours)",
            token_lifetime,
            token_lifetime / 3600,
        )

    # ─── Authentication ──────────────────────────────────────────────

    async def authenticate_with_password(self, username: str, password: str) -> dict[str, Any]:
        """Authenticate using username and password via Auth0 PKCE flow."""
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip("=")
        state = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        nonce = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")

        try:
            # Step 1: Authorize → get auth state
            authorize_params = {
                "client_id": OAUTH_CLIENT_ID,
                "response_type": "code",
                "redirect_uri": OAUTH_REDIRECT_URI,
                "scope": " ".join(OAUTH_SCOPES),
                "audience": OAUTH_AUDIENCE,
                "state": state,
                "nonce": nonce,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
            authorize_url = OAUTH_AUTHORIZE_URL + "?" + urlencode(authorize_params)

            async with self._session.get(authorize_url, allow_redirects=False) as response:
                if response.status in [302, 303]:
                    location = response.headers.get("Location", "")
                    query_params = parse_qs(urlparse(location).query)
                    auth_state = query_params.get("state", [state])[0]
                else:
                    auth_state = state

            # Step 2: Submit credentials
            login_payload = {
                "client_id": OAUTH_CLIENT_ID,
                "redirect_uri": OAUTH_REDIRECT_URI,
                "tenant": "ovoenergyau",
                "response_type": "code",
                "scope": " ".join(OAUTH_SCOPES),
                "audience": OAUTH_AUDIENCE,
                "state": auth_state,
                "nonce": nonce,
                "username": username,
                "password": password,
                "connection": OAUTH_CONNECTION,
            }
            headers = {
                "content-type": "application/json",
                "origin": AUTH_BASE_URL,
                "referer": authorize_url,
            }

            async with self._session.post(
                OAUTH_LOGIN_URL, json=login_payload, headers=headers
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise OVOEnergyAUApiClientAuthenticationError(
                        f"Login failed: {text[:200]}"
                    )
                text = await response.text()

            # Step 3: Parse HTML form response
            action_match = re.search(r'action="([^"]+)"', text)
            if not action_match:
                raise OVOEnergyAUApiClientAuthenticationError(
                    "Could not find form action in response"
                )

            form_action = html.unescape(action_match.group(1))
            form_data = {}
            for match in re.finditer(
                r'<input[^>]+type="hidden"[^>]+name="([^"]+)"[^>]+value="([^"]*)"',
                text,
                re.DOTALL,
            ):
                form_data[match.group(1)] = html.unescape(match.group(2))

            if not form_data:
                raise OVOEnergyAUApiClientAuthenticationError(
                    "No hidden fields found in login response"
                )

            # Step 4: Submit form → get authorization code
            async with self._session.post(
                form_action,
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                allow_redirects=True,
            ) as response:
                final_url = str(response.url)
                query_params = parse_qs(urlparse(final_url).query)

                if "error" in query_params:
                    error_code = query_params.get("error", ["unknown"])[0]
                    error_desc = query_params.get("error_description", ["No description"])[0]
                    raise OVOEnergyAUApiClientAuthenticationError(
                        f"Authentication failed: {error_code} - {error_desc}"
                    )

                authorization_code = query_params.get("code", [None])[0]
                if not authorization_code:
                    raise OVOEnergyAUApiClientAuthenticationError(
                        "Could not extract authorization code from callback"
                    )

            # Step 5: Exchange code for tokens
            token_data = await self._exchange_code_for_tokens(
                authorization_code, OAUTH_REDIRECT_URI, code_verifier
            )
            _LOGGER.info("Successfully authenticated with username/password")
            return token_data

        except OVOEnergyAUApiClientError:
            raise
        except Exception as err:
            _LOGGER.error("Authentication error: %s", err)
            raise OVOEnergyAUApiClientAuthenticationError(
                f"Authentication failed: {err}"
            ) from err

    async def _exchange_code_for_tokens(
        self, code: str, redirect_uri: str, code_verifier: str
    ) -> dict[str, Any]:
        """Exchange authorization code for tokens."""
        data = {
            "grant_type": "authorization_code",
            "client_id": OAUTH_CLIENT_ID,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
        try:
            async with self._session.post(OAUTH_TOKEN_URL, json=data) as response:
                response.raise_for_status()
                token_data = await response.json()
                self.set_tokens(
                    access_token=token_data["access_token"],
                    id_token=token_data["id_token"],
                    refresh_token=token_data.get("refresh_token"),
                    expires_in=token_data.get("expires_in"),
                )
                return token_data
        except aiohttp.ClientError as err:
            raise OVOEnergyAUApiClientCommunicationError(
                "Error communicating with Auth0"
            ) from err
        except Exception as err:
            raise OVOEnergyAUApiClientAuthenticationError(
                "Error exchanging code for tokens"
            ) from err

    async def refresh_tokens(self) -> dict[str, Any]:
        """Refresh access token using refresh token."""
        if not self._refresh_token:
            raise OVOEnergyAUApiClientAuthenticationError("No refresh token available")

        data = {
            "grant_type": "refresh_token",
            "client_id": OAUTH_CLIENT_ID,
            "refresh_token": self._refresh_token,
        }
        try:
            async with self._session.post(OAUTH_TOKEN_URL, json=data) as response:
                response.raise_for_status()
                token_data = await response.json()
                self.set_tokens(
                    access_token=token_data["access_token"],
                    id_token=token_data["id_token"],
                    refresh_token=token_data.get("refresh_token", self._refresh_token),
                    expires_in=token_data.get("expires_in"),
                )
                return token_data
        except aiohttp.ClientResponseError as err:
            if err.status in (401, 403):
                raise OVOEnergyAUApiClientAuthenticationError(
                    "Refresh token expired or invalid - please re-authenticate"
                ) from err
            raise OVOEnergyAUApiClientCommunicationError("Error refreshing tokens") from err
        except aiohttp.ClientError as err:
            raise OVOEnergyAUApiClientCommunicationError("Error refreshing tokens") from err

    # ─── Internal helpers ────────────────────────────────────────────

    async def _ensure_authenticated(self) -> None:
        """Ensure the client is authenticated, refreshing if needed."""
        async with self._refresh_lock:
            if not self._access_token:
                if self._username and self._password:
                    await self.authenticate_with_password(self._username, self._password)
                    return
                raise OVOEnergyAUApiClientAuthenticationError("Not authenticated")

            if self.should_refresh:
                # Prefer full re-auth (more reliable than refresh tokens)
                if self._username and self._password:
                    try:
                        await self.authenticate_with_password(self._username, self._password)
                        return
                    except (OVOEnergyAUApiClientError, aiohttp.ClientError) as err:
                        _LOGGER.warning("Re-auth failed, falling back to refresh: %s", err)

                if self._refresh_token:
                    await self.refresh_tokens()
                else:
                    raise OVOEnergyAUApiClientAuthenticationError(
                        "Token needs refresh but no refresh mechanism available"
                    )

    async def _rate_limit(self) -> None:
        """Apply rate limiting between API requests."""
        async with self._rate_limit_lock:
            if self._last_request_time is not None:
                elapsed = time.time() - self._last_request_time
                if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
                    await asyncio.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)
            self._last_request_time = time.time()

    def _graphql_headers(self, referer_path: str = "/") -> dict[str, str]:
        """Build standard GraphQL request headers."""
        return {
            "accept": "*/*",
            "authorization": self._access_token,
            "content-type": "application/json",
            "myovo-id-token": self._id_token,
            "origin": API_BASE_URL,
            "referer": f"{API_BASE_URL}{referer_path}",
        }

    async def _graphql_request(
        self,
        operation_name: str,
        query: str,
        variables: dict[str, Any],
        result_key: str,
        referer_path: str = "/",
        allow_null_result: bool = False,
    ) -> dict[str, Any] | None:
        """Execute a GraphQL request with unified error handling.

        This eliminates the 30-line copy-pasted error handling from each API method.

        Args:
            operation_name: GraphQL operation name
            query: GraphQL query string
            variables: Query variables
            result_key: Key to extract from data (e.g., "GetIntervalData")
            referer_path: Referer path for headers
            allow_null_result: If True, return {} instead of raising on null result

        Returns:
            The extracted result data

        Raises:
            OVOEnergyAUApiClientAuthenticationError: On auth failures
            OVOEnergyAUApiClientCommunicationError: On network failures
            OVOEnergyAUApiClientError: On GraphQL errors
        """
        await self._ensure_authenticated()
        await self._rate_limit()

        payload = {
            "operationName": operation_name,
            "variables": variables,
            "query": query,
        }

        try:
            async with self._session.post(
                GRAPHQL_URL,
                json=payload,
                headers=self._graphql_headers(referer_path),
            ) as response:
                response.raise_for_status()

                content_type = response.headers.get("Content-Type", "")
                if "application/json" not in content_type:
                    _LOGGER.error(
                        "API returned %s instead of JSON - likely expired tokens",
                        content_type,
                    )
                    raise OVOEnergyAUApiClientAuthenticationError(
                        "Token expired or invalid - please re-authenticate"
                    )

                data = await response.json()

                # Check for GraphQL errors
                if "errors" in data and data["errors"]:
                    error_messages = [
                        error.get("message", "Unknown error")
                        for error in data["errors"]
                        if isinstance(error, dict)
                    ]
                    if error_messages:
                        raise OVOEnergyAUApiClientError(
                            f"GraphQL errors: {', '.join(error_messages)}"
                        )

                # Extract result
                if "data" not in data or data["data"] is None:
                    if allow_null_result:
                        return {}
                    raise OVOEnergyAUApiClientError("Invalid response from API")

                result = data["data"].get(result_key)
                if result is None:
                    if allow_null_result:
                        _LOGGER.info(
                            "%s returned null - data may not be available", result_key
                        )
                        return {}
                    raise OVOEnergyAUApiClientError(
                        f"Missing {result_key} in response"
                    )

                return result

        except OVOEnergyAUApiClientError:
            raise
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                raise OVOEnergyAUApiClientAuthenticationError(
                    "Authentication failed"
                ) from err
            raise OVOEnergyAUApiClientCommunicationError(
                f"Error communicating with API: {err}"
            ) from err
        except aiohttp.ContentTypeError as err:
            raise OVOEnergyAUApiClientAuthenticationError(
                "Token expired or invalid - API returned HTML instead of JSON"
            ) from err
        except aiohttp.ClientError as err:
            raise OVOEnergyAUApiClientCommunicationError(
                f"Error communicating with API: {err}"
            ) from err

    # ─── Public API methods ──────────────────────────────────────────

    async def get_contact_info(self) -> dict[str, Any]:
        """Get contact information and account details."""
        await self._ensure_authenticated()
        try:
            decoded_id = jwt.decode(self._id_token, options={"verify_signature": False})
            email = decoded_id.get("email")
            if not email:
                raise OVOEnergyAUApiClientError("Email not found in ID token")
        except OVOEnergyAUApiClientError:
            raise
        except Exception as err:
            raise OVOEnergyAUApiClientError(f"Error decoding ID token: {err}") from err

        return await self._graphql_request(
            operation_name="GetContactInfo",
            query=GET_CONTACT_INFO,
            variables={"input": {"email": email}},
            result_key="GetContactInfo",
        )

    async def get_account_ids(self) -> list[str]:
        """Get all active account IDs."""
        contact_info = await self.get_contact_info()
        accounts = contact_info.get("accounts", [])
        active = [a for a in accounts if not a.get("closed", False)]
        if not active:
            raise OVOEnergyAUApiClientError("No active accounts found")
        return [str(a["id"]) for a in active]

    async def get_account_id(self) -> str:
        """Get the primary active account ID."""
        ids = await self.get_account_ids()
        return ids[0]

    async def get_interval_data(self, account_id: str) -> dict[str, Any]:
        """Get interval data (daily/monthly/yearly) for an account."""
        return await self._graphql_request(
            operation_name="GetIntervalData",
            query=GET_INTERVAL_DATA,
            variables={"input": {"accountId": account_id}},
            result_key="GetIntervalData",
            referer_path="/usage",
        )

    async def get_hourly_data(
        self, account_id: str, start_date: str, end_date: str
    ) -> dict[str, Any]:
        """Get hourly data for a date range (YYYY-MM-DD format)."""
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as err:
            raise OVOEnergyAUApiClientError(
                f"Invalid date format (expected YYYY-MM-DD): {err}"
            ) from err

        return await self._graphql_request(
            operation_name="GetHourlyData",
            query=GET_HOURLY_DATA,
            variables={
                "input": {
                    "accountId": account_id,
                    "dateRange": {"startDate": start_date, "endDate": end_date},
                }
            },
            result_key="GetHourlyData",
            referer_path="/usage",
            allow_null_result=True,
        )

    async def get_product_agreements(self, account_id: str) -> dict[str, Any]:
        """Get product agreements (plan information) for an account."""
        result = await self._graphql_request(
            operation_name="GetProductAgreements",
            query=GET_PRODUCT_AGREEMENTS,
            variables={"input": {"id": account_id, "system": "KALUZA"}},
            result_key="GetAccountInfo",
            referer_path="/usage",
        )
        _LOGGER.info("Fetched product agreements for account %s", result.get("id"))
        return result

    async def test_connection(self, account_id: str) -> bool:
        """Test the API connection."""
        try:
            await self.get_interval_data(account_id)
            return True
        except Exception as err:
            _LOGGER.error("Connection test failed: %s", err)
            return False
