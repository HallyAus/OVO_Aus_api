"""API client for OVO Energy Australia."""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta
import hashlib
import html
import logging
import re
import secrets
from typing import Any
from urllib.parse import parse_qs, urlparse

import aiohttp
import jwt

from .const import (
    API_BASE_URL,
    AUTH_BASE_URL,
    GET_ACCOUNT_INFO_QUERY,
    GET_CONTACT_INFO_QUERY,
    GET_HOURLY_DATA_QUERY,
    GET_INTERVAL_DATA_QUERY,
    GRAPHQL_URL,
    OAUTH_AUDIENCE,
    OAUTH_AUTHORIZE_URL,
    OAUTH_CLIENT_ID,
    OAUTH_CONNECTION,
    OAUTH_LOGIN_URL,
    OAUTH_REDIRECT_URI,
    OAUTH_SCOPES,
    OAUTH_TOKEN_URL,
)

_LOGGER = logging.getLogger(__name__)


class OVOEnergyAUApiClientError(Exception):
    """Exception to indicate a general API error."""


class OVOEnergyAUApiClientAuthenticationError(OVOEnergyAUApiClientError):
    """Exception to indicate an authentication error."""


class OVOEnergyAUApiClientCommunicationError(OVOEnergyAUApiClientError):
    """Exception to indicate a communication error."""


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

    @property
    def is_authenticated(self) -> bool:
        """Return True if the client is authenticated."""
        return self._access_token is not None and not self.token_expired

    @property
    def token_expired(self) -> bool:
        """Return True if the token has expired (actually expired, no buffer)."""
        if self._token_expires_at is None:
            return True
        return datetime.now() >= self._token_expires_at

    @property
    def should_refresh(self) -> bool:
        """Return True if the token should be refreshed (with adaptive buffer)."""
        if self._token_expires_at is None:
            return True

        # Calculate token lifetime to use adaptive buffer
        # Use 20% of token lifetime or 2 minutes, whichever is smaller
        now = datetime.now()
        if hasattr(self, '_token_created_at') and self._token_created_at:
            token_lifetime = (self._token_expires_at - self._token_created_at).total_seconds()
            buffer_seconds = min(token_lifetime * 0.2, 120)  # 20% or 2 min max
        else:
            # Fallback to 1 minute buffer if we don't know when token was created
            buffer_seconds = 60

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
        self._token_created_at = datetime.now()

        if expires_in:
            self._token_expires_at = self._token_created_at + timedelta(seconds=expires_in)
        else:
            # Try to decode the JWT to get expiration
            try:
                decoded = jwt.decode(
                    access_token,
                    options={"verify_signature": False},
                )
                exp_timestamp = decoded.get("exp")
                if exp_timestamp:
                    self._token_expires_at = datetime.fromtimestamp(exp_timestamp)
                else:
                    # Default to 1 hour
                    self._token_expires_at = self._token_created_at + timedelta(hours=1)
            except Exception:
                # Default to 1 hour
                self._token_expires_at = self._token_created_at + timedelta(hours=1)

        token_lifetime = (self._token_expires_at - self._token_created_at).total_seconds()
        _LOGGER.debug(
            "Tokens set, expires at: %s (lifetime: %.0f seconds)",
            self._token_expires_at,
            token_lifetime
        )

    async def exchange_code_for_tokens(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: str,
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
            # 403 Forbidden means refresh token is expired or invalid
            if err.status == 403:
                raise OVOEnergyAUApiClientAuthenticationError(
                    "Refresh token expired or invalid - please re-authenticate"
                ) from err
            raise OVOEnergyAUApiClientCommunicationError(
                "Error refreshing tokens"
            ) from err
        except aiohttp.ClientError as err:
            raise OVOEnergyAUApiClientCommunicationError(
                "Error refreshing tokens"
            ) from err
        except Exception as err:
            raise OVOEnergyAUApiClientAuthenticationError(
                "Error refreshing tokens"
            ) from err

    async def authenticate_with_password(
        self,
        username: str,
        password: str,
    ) -> dict[str, Any]:
        """Authenticate using username and password via Auth0."""
        # Generate PKCE parameters
        code_verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')

        state = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        nonce = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

        _LOGGER.debug("Starting Auth0 authentication flow")

        try:
            # Step 1: Initial authorize request to get auth state
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

            authorize_url = OAUTH_AUTHORIZE_URL + "?" + "&".join(
                f"{k}={v}" for k, v in authorize_params.items()
            )

            # Get the authorize page to establish session
            async with self._session.get(authorize_url, allow_redirects=False) as response:
                if response.status in [302, 303]:
                    location = response.headers.get('Location', '')
                    parsed = urlparse(location)
                    query_params = parse_qs(parsed.query)
                    auth_state = query_params.get('state', [state])[0]
                else:
                    auth_state = state

            _LOGGER.debug("Got auth state, submitting credentials")

            # Step 2: Submit username/password to login endpoint
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
                OAUTH_LOGIN_URL,
                json=login_payload,
                headers=headers,
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise OVOEnergyAUApiClientAuthenticationError(
                        f"Login failed: {text[:200]}"
                    )

                # Auth0 Universal Login returns HTML form that needs to be submitted
                text = await response.text()
                _LOGGER.debug("Login response received, length: %d", len(text))

            # Step 3: Parse the HTML form response and extract hidden fields
            _LOGGER.debug("Parsing form response")

            # Extract form action URL
            action_match = re.search(r'action="([^"]+)"', text)
            if not action_match:
                raise OVOEnergyAUApiClientAuthenticationError(
                    "Could not find form action in response"
                )

            form_action = html.unescape(action_match.group(1))

            # Extract hidden field values (handle multi-line and HTML entities)
            form_data = {}
            for match in re.finditer(
                r'<input[^>]+type="hidden"[^>]+name="([^"]+)"[^>]+value="([^"]*)"',
                text,
                re.DOTALL
            ):
                field_name = match.group(1)
                field_value = html.unescape(match.group(2))
                form_data[field_name] = field_value

            if not form_data:
                raise OVOEnergyAUApiClientAuthenticationError(
                    "No hidden fields found in login response"
                )

            _LOGGER.debug("Found %d form fields", len(form_data))

            # Step 4: Submit the form to the callback URL
            _LOGGER.debug("Submitting form to callback")
            async with self._session.post(
                form_action,
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                allow_redirects=True
            ) as response:
                # Follow redirects until we get to the final callback with the code
                final_url = str(response.url)
                parsed = urlparse(final_url)
                query_params = parse_qs(parsed.query)

                _LOGGER.debug("Callback URL: %s", final_url)
                _LOGGER.debug("Query params: %s", list(query_params.keys()))

                # Check for Auth0 error responses
                if 'error' in query_params:
                    error_code = query_params.get('error', ['unknown'])[0]
                    error_desc = query_params.get('error_description', ['No description'])[0]
                    _LOGGER.error("Auth0 error: %s - %s", error_code, error_desc)
                    raise OVOEnergyAUApiClientAuthenticationError(
                        f"Authentication failed: {error_code} - {error_desc}"
                    )

                authorization_code = query_params.get('code', [None])[0]
                if not authorization_code:
                    _LOGGER.error(
                        "No authorization code in callback. URL: %s, Params: %s",
                        final_url,
                        query_params
                    )
                    raise OVOEnergyAUApiClientAuthenticationError(
                        "Could not extract authorization code from callback. "
                        "Check credentials or try again."
                    )

                _LOGGER.debug("Got authorization code, exchanging for tokens")

            # Step 5: Exchange authorization code for tokens
            token_data = await self.exchange_code_for_tokens(
                code=authorization_code,
                redirect_uri=OAUTH_REDIRECT_URI,
                code_verifier=code_verifier,
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

    async def _ensure_authenticated(self) -> None:
        """Ensure the client is authenticated."""
        if not self._access_token:
            # If we have credentials, try to authenticate
            if self._username and self._password:
                _LOGGER.debug("No access token, authenticating with credentials")
                await self.authenticate_with_password(self._username, self._password)
                return
            raise OVOEnergyAUApiClientAuthenticationError("Not authenticated")

        # Use should_refresh which includes 5-minute buffer for proactive refresh
        if self.should_refresh:
            _LOGGER.debug("Token expiring soon, refreshing...")
            
            # Prefer full re-authentication if we have credentials
            # This is more reliable than refresh tokens which seem to expire/invalidate after 24h
            if self._username and self._password:
                try:
                    _LOGGER.debug("Performing full re-authentication with password")
                    await self.authenticate_with_password(self._username, self._password)
                    _LOGGER.debug("Re-authentication successful")
                    return
                except Exception as err:
                    _LOGGER.warning("Re-authentication failed: %s. Falling back to refresh token.", err)
            
            # Fallback to refresh token if no credentials or re-auth failed
            if self._refresh_token:
                await self.refresh_tokens()
                _LOGGER.debug("Token refreshed successfully")

    async def get_contact_info(self) -> dict[str, Any]:
        """Get contact information and account details."""
        await self._ensure_authenticated()

        # Extract email from ID token
        try:
            decoded_id = jwt.decode(
                self._id_token,
                options={"verify_signature": False},
            )
            email = decoded_id.get('email')
            if not email:
                raise OVOEnergyAUApiClientError("Email not found in ID token")
        except Exception as err:
            raise OVOEnergyAUApiClientError(
                f"Error decoding ID token: {err}"
            ) from err

        headers = {
            "accept": "*/*",
            "authorization": f"Bearer {self._access_token}",
            "content-type": "application/json",
            "myovo-id-token": self._id_token,
            "origin": API_BASE_URL,
            "referer": f"{API_BASE_URL}/",
        }

        payload = {
            "operationName": "GetContactInfo",
            "variables": {
                "input": {
                    "email": email
                }
            },
            "query": GET_CONTACT_INFO_QUERY
        }

        try:
            async with self._session.post(
                GRAPHQL_URL,
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()

                # Check content type before trying to parse JSON
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    # API returned HTML instead of JSON - likely due to auth redirect
                    _LOGGER.error(
                        "API returned HTML instead of JSON (Content-Type: %s). "
                        "This usually indicates expired or invalid tokens.",
                        content_type
                    )
                    raise OVOEnergyAUApiClientAuthenticationError(
                        "Token expired or invalid - please re-authenticate"
                    )

                data = await response.json()

                if "errors" in data:
                    error_messages = [error.get("message", "Unknown error") for error in data["errors"]]
                    raise OVOEnergyAUApiClientError(f"GraphQL errors: {', '.join(error_messages)}")

                if "data" not in data or "GetContactInfo" not in data["data"]:
                    raise OVOEnergyAUApiClientError("Invalid response from API")

                return data["data"]["GetContactInfo"]
        except OVOEnergyAUApiClientAuthenticationError:
            # Re-raise authentication errors without wrapping
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
            # This is the exact error Home Assistant was getting
            raise OVOEnergyAUApiClientAuthenticationError(
                "Token expired or invalid - API returned HTML instead of JSON"
            ) from err
        except aiohttp.ClientError as err:
            raise OVOEnergyAUApiClientCommunicationError(
                f"Error communicating with API: {err}"
            ) from err

    async def get_account_ids(self) -> list[str]:
        """Get all account IDs for the user."""
        contact_info = await self.get_contact_info()
        accounts = contact_info.get("accounts", [])

        # Filter for active (non-closed) accounts
        active_accounts = [a for a in accounts if not a.get("closed", False)]

        if not active_accounts:
            raise OVOEnergyAUApiClientError("No active accounts found")

        return [str(account["id"]) for account in active_accounts]

    async def get_account_id(self) -> str:
        """Get the primary (first) active account ID."""
        account_ids = await self.get_account_ids()
        if not account_ids:
            raise OVOEnergyAUApiClientError("No account IDs found")
        return account_ids[0]

    async def get_interval_data(self, account_id: str) -> dict[str, Any]:
        """Get interval data for an account."""
        await self._ensure_authenticated()

        headers = {
            "accept": "*/*",
            "authorization": f"Bearer {self._access_token}",
            "content-type": "application/json",
            "myovo-id-token": self._id_token,
            "origin": API_BASE_URL,
            "referer": f"{API_BASE_URL}/usage",
        }

        payload = {
            "operationName": "GetIntervalData",
            "variables": {
                "input": {
                    "accountId": account_id
                }
            },
            "query": GET_INTERVAL_DATA_QUERY
        }

        try:
            async with self._session.post(
                GRAPHQL_URL,
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()

                # Check content type before trying to parse JSON
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    _LOGGER.error(
                        "API returned HTML instead of JSON (Content-Type: %s). "
                        "This usually indicates expired or invalid tokens.",
                        content_type
                    )
                    raise OVOEnergyAUApiClientAuthenticationError(
                        "Token expired or invalid - please re-authenticate"
                    )

                data = await response.json()

                if "errors" in data:
                    error_messages = [error.get("message", "Unknown error") for error in data["errors"]]
                    raise OVOEnergyAUApiClientError(f"GraphQL errors: {', '.join(error_messages)}")

                if "data" not in data:
                    raise OVOEnergyAUApiClientError("Invalid response from API")

                return data["data"]["GetIntervalData"]
        except OVOEnergyAUApiClientAuthenticationError:
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

    async def get_hourly_data(
        self,
        account_id: str,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """Get hourly data for an account within a date range.

        Args:
            account_id: The account ID
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
        """
        await self._ensure_authenticated()

        headers = {
            "accept": "*/*",
            "authorization": f"Bearer {self._access_token}",
            "content-type": "application/json",
            "myovo-id-token": self._id_token,
            "origin": API_BASE_URL,
            "referer": f"{API_BASE_URL}/usage",
        }

        payload = {
            "operationName": "GetHourlyData",
            "variables": {
                "input": {
                    "accountId": account_id,
                    "dateRange": {
                        "startDate": start_date,
                        "endDate": end_date,
                    }
                }
            },
            "query": GET_HOURLY_DATA_QUERY
        }

        try:
            async with self._session.post(
                GRAPHQL_URL,
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()

                # Check content type before trying to parse JSON
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    _LOGGER.error(
                        "API returned HTML instead of JSON (Content-Type: %s). "
                        "This usually indicates expired or invalid tokens.",
                        content_type
                    )
                    raise OVOEnergyAUApiClientAuthenticationError(
                        "Token expired or invalid - please re-authenticate"
                    )

                data = await response.json()

                if "errors" in data:
                    error_messages = [error.get("message", "Unknown error") for error in data["errors"]]
                    raise OVOEnergyAUApiClientError(f"GraphQL errors: {', '.join(error_messages)}")

                if "data" not in data:
                    raise OVOEnergyAUApiClientError("Invalid response from API")

                return data["data"]["GetHourlyData"]
        except OVOEnergyAUApiClientAuthenticationError:
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

    async def get_product_agreements(self, account_id: str) -> dict[str, Any]:
        """Get product agreements (plan information) for an account.

        Returns plan details including:
        - displayName: Name of the plan (e.g., "The EV Plan")
        - standingChargeCentsPerDay: Daily standing charge in cents
        - unitRatesCentsPerKWH: Dictionary of rates in cents per kWh
            - peak, offPeak, shoulder, evOffPeak, superOffPeak, feedInTariff, etc.
        - fromDt/toDt: Agreement validity period
        - nmi: National Meter Identifier
        """
        await self._ensure_authenticated()

        headers = {
            "accept": "*/*",
            "authorization": f"Bearer {self._access_token}",
            "content-type": "application/json",
            "myovo-id-token": self._id_token,
            "origin": API_BASE_URL,
            "referer": f"{API_BASE_URL}/usage",
        }

        payload = {
            "operationName": "GetAccountInfo",
            "variables": {},
            "query": GET_ACCOUNT_INFO_QUERY
        }

        try:
            async with self._session.post(
                GRAPHQL_URL,
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()

                # Check content type before trying to parse JSON
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    _LOGGER.error(
                        "API returned HTML instead of JSON (Content-Type: %s). "
                        "This usually indicates expired or invalid tokens.",
                        content_type
                    )
                    raise OVOEnergyAUApiClientAuthenticationError(
                        "Token expired or invalid - please re-authenticate"
                    )

                data = await response.json()

                if "errors" in data:
                    error_messages = [error.get("message", "Unknown error") for error in data["errors"]]
                    raise OVOEnergyAUApiClientError(f"GraphQL errors: {', '.join(error_messages)}")

                if "data" not in data or "GetAccountInfo" not in data["data"]:
                    raise OVOEnergyAUApiClientError("Invalid response from API")

                return data["data"]["GetAccountInfo"]
        except OVOEnergyAUApiClientAuthenticationError:
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

    async def test_connection(self, account_id: str) -> bool:
        """Test the connection to the API."""
        try:
            await self.get_interval_data(account_id)
            return True
        except Exception as err:
            _LOGGER.error("Connection test failed: %s", err)
            return False
