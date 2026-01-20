"""
OVO Energy Australia API Client for Home Assistant

Simplified version of the main client for Home Assistant integration.
"""

import requests
import logging
import json
import hashlib
import secrets
import base64
from datetime import datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse, parse_qs, urlencode

_LOGGER = logging.getLogger(__name__)


# PKCE Helper Functions
def _generate_code_verifier() -> str:
    """Generate a code verifier for PKCE flow"""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8')
    return code_verifier.rstrip('=')


def _generate_code_challenge(code_verifier: str) -> str:
    """Generate a code challenge from the code verifier for PKCE flow"""
    code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8')
    return code_challenge.rstrip('=')


class OVOAuthenticationError(Exception):
    """Raised when authentication fails"""
    pass


class OVOAPIError(Exception):
    """Raised when API requests fail"""
    pass


class OVOTokenExpiredError(Exception):
    """Raised when access tokens have expired"""
    pass


class OVOEnergyAU:
    """OVO Energy Australia API Client (Home Assistant version)"""

    API_URL = "https://my.ovoenergy.com.au/graphql"
    AUTH0_DOMAIN = "https://login.ovoenergy.com.au"
    CLIENT_ID = "5JHnPn71qgV3LmF3I3xX0KvfRBdROVhR"

    def __init__(self, access_token: Optional[str] = None,
                 id_token: Optional[str] = None,
                 account_id: Optional[str] = None,
                 refresh_token: Optional[str] = None,
                 token_update_callback=None):
        """Initialize the client

        Args:
            access_token: Access token (with Bearer prefix)
            id_token: ID token
            account_id: OVO account ID
            refresh_token: Refresh token for automatic token renewal
            token_update_callback: Callback function(access_token, id_token, refresh_token)
                                  called when tokens are refreshed
        """
        self._access_token = access_token
        self._id_token = id_token
        self._refresh_token = refresh_token
        self.account_id = account_id
        self._token_update_callback = token_update_callback

        self.session = requests.Session()
        self._update_session_headers()

    def _update_session_headers(self):
        """Update session headers with current tokens"""
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Origin': 'https://my.ovoenergy.com.au',
            'Referer': 'https://my.ovoenergy.com.au/usage',
            'User-Agent': 'Mozilla/5.0 (Home Assistant)'
        })

        if self._access_token:
            self.session.headers['authorization'] = self._access_token
        if self._id_token:
            self.session.headers['myovo-id-token'] = self._id_token

    def set_tokens(self, access_token: str, id_token: str, refresh_token: Optional[str] = None):
        """Set authentication tokens"""
        self._access_token = access_token
        self._id_token = id_token
        if refresh_token:
            self._refresh_token = refresh_token
        self._update_session_headers()

    def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate with OVO Energy Australia using OAuth 2.0 PKCE flow

        Based on working implementation from Mattallmighty/HA-OvoEnergyAU
        """
        import re
        import html as html_module

        _LOGGER.info("Authenticating with OVO Energy using PKCE flow for user: %s", username)

        try:
            # Step 1: Generate PKCE parameters
            code_verifier = _generate_code_verifier()
            code_challenge = _generate_code_challenge(code_verifier)
            state = secrets.token_urlsafe(32)
            nonce = secrets.token_urlsafe(32)

            # Step 2: Initial authorization request to establish session
            auth_params = {
                "client_id": self.CLIENT_ID,
                "response_type": "code",
                "redirect_uri": "https://my.ovoenergy.com.au?login=oea",
                "scope": "openid profile email offline_access",
                "audience": "https://login.ovoenergy.com.au/api",
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "state": state,
                "nonce": nonce,
                "connection": "prod-myovo-auth"  # CRITICAL: This is the key!
            }

            auth_url = f"{self.AUTH0_DOMAIN}/authorize?" + urlencode(auth_params)

            session = requests.Session()
            auth_response = session.get(auth_url, allow_redirects=False, timeout=30)

            _LOGGER.debug("Authorization request status: %s", auth_response.status_code)

            # Extract state from the response
            auth_state = state
            if auth_response.status_code == 302 and 'location' in auth_response.headers:
                location = auth_response.headers['location']
                parsed = urlparse(location)
                query = parse_qs(parsed.query)
                if 'state' in query:
                    auth_state = query['state'][0]

            # Step 3: Submit credentials to login endpoint
            login_payload = {
                "client_id": self.CLIENT_ID,
                "username": username,
                "password": password,
                "credential_type": "http://auth0.com/oauth/grant-type/password-realm",
                "realm": "prod-myovo-auth",  # CRITICAL: Must match connection!
                "connection": "prod-myovo-auth",
                "state": auth_state
            }

            _LOGGER.debug("Submitting credentials to login endpoint")
            login_response = session.post(
                f"{self.AUTH0_DOMAIN}/usernamepassword/login",
                json=login_payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            _LOGGER.debug("Login response status: %s", login_response.status_code)

            if login_response.status_code != 200:
                _LOGGER.error("Login failed with status %s: %s",
                            login_response.status_code, login_response.text[:500])
                raise OVOAuthenticationError(f"Login failed: {login_response.status_code}")

            # Step 4: Parse HTML form from response
            html_content = login_response.text

            # Extract form action URL using regex
            form_action_match = re.search(r'<form[^>]*action="([^"]*)"', html_content)
            if not form_action_match:
                _LOGGER.error("Could not find form action in login response")
                raise OVOAuthenticationError("Invalid response from login endpoint")

            form_action = html_module.unescape(form_action_match.group(1))
            _LOGGER.debug("Form action URL: %s", form_action)

            # Extract all hidden input fields
            form_data = {}
            for match in re.finditer(r'<input[^>]*type="hidden"[^>]*name="([^"]*)"[^>]*value="([^"]*)"', html_content):
                field_name = html_module.unescape(match.group(1))
                field_value = html_module.unescape(match.group(2))
                form_data[field_name] = field_value

            _LOGGER.debug("Found %d hidden form fields", len(form_data))

            # Step 5: Submit form to callback and extract authorization code
            _LOGGER.debug("Submitting form to callback")
            form_response = session.post(
                form_action,
                data=form_data,
                allow_redirects=True,
                timeout=30
            )

            # Look for authorization code in URL of final redirect
            auth_code = None
            for resp in [form_response] + list(getattr(form_response, 'history', [])):
                if "code=" in resp.url:
                    parsed = urlparse(resp.url)
                    query_params = parse_qs(parsed.query)
                    if "code" in query_params:
                        auth_code = query_params["code"][0]
                        _LOGGER.debug("Authorization code found in redirect")
                        break

            if not auth_code:
                _LOGGER.error("No authorization code found in OAuth flow")
                # Log the final URL for debugging
                _LOGGER.error("Final URL: %s", form_response.url)
                raise OVOAuthenticationError("Failed to obtain authorization code")

            _LOGGER.debug("Exchanging authorization code for tokens...")

            # Exchange code for tokens
            return self._exchange_code_for_tokens(auth_code, code_verifier)

        except OVOAuthenticationError:
            raise
        except Exception as e:
            _LOGGER.exception("Unexpected error during authentication: %s", e)
            raise OVOAuthenticationError(f"Authentication failed: {e}")

    def _exchange_code_for_tokens(self, auth_code: str, code_verifier: str) -> bool:
        """Exchange authorization code for tokens"""
        _LOGGER.debug("Exchanging authorization code for tokens")

        token_url = f"{self.AUTH0_DOMAIN}/oauth/token"

        payload = {
            "grant_type": "authorization_code",
            "client_id": self.CLIENT_ID,
            "code": auth_code,
            "code_verifier": code_verifier,
            "redirect_uri": "https://my.ovoenergy.com.au/login/callback"
        }

        try:
            response = requests.post(
                token_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code == 200:
                tokens = response.json()
                return self._process_tokens(tokens)

            _LOGGER.debug("Token exchange failed with status %s: %s", response.status_code, response.text)
            return False

        except Exception as e:
            _LOGGER.debug("Token exchange exception: %s", e)
            return False

    def _process_tokens(self, tokens: Dict[str, Any]) -> bool:
        """Process and store authentication tokens"""
        access_token = tokens.get("access_token")
        id_token = tokens.get("id_token")
        refresh_token = tokens.get("refresh_token")

        if not access_token or not id_token:
            _LOGGER.error("Missing required tokens in response")
            return False

        # Add "Bearer " prefix if not present
        if not access_token.startswith("Bearer "):
            access_token = f"Bearer {access_token}"

        self._access_token = access_token
        self._id_token = id_token
        self._refresh_token = refresh_token

        self._update_session_headers()

        # Try to extract account_id from ID token if not already set
        if not self.account_id:
            self.account_id = self._extract_account_id_from_token(id_token)

        _LOGGER.info("Tokens successfully processed and stored")
        return True

    def _extract_account_id_from_token(self, id_token: str) -> Optional[str]:
        """Attempt to extract account_id from ID token"""
        try:
            parts = id_token.split('.')
            if len(parts) != 3:
                return None

            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding

            decoded = base64.urlsafe_b64decode(payload)
            payload_data = json.loads(decoded)

            for field in ['account_id', 'accountId', 'sub', 'user_id']:
                if field in payload_data:
                    value = str(payload_data[field])
                    if value.isdigit():
                        _LOGGER.info("Extracted account_id from token: %s", value)
                        return value

            _LOGGER.debug("Could not find account_id in ID token")
            return None

        except Exception as e:
            _LOGGER.debug("Failed to extract account_id from token: %s", e)
            return None

    def refresh_tokens(self) -> bool:
        """Refresh access and ID tokens using refresh token

        Returns:
            True if refresh was successful, False otherwise
        """
        if not self._refresh_token:
            _LOGGER.warning("No refresh token available, cannot refresh tokens")
            return False

        token_url = f"{self.AUTH0_DOMAIN}/oauth/token"

        payload = {
            "grant_type": "refresh_token",
            "client_id": self.CLIENT_ID,
            "refresh_token": self._refresh_token,
            "redirect_uri": "https://my.ovoenergy.com.au?login=oea"
        }

        try:
            _LOGGER.info("Refreshing tokens...")
            response = self.session.post(
                token_url,
                data=payload,  # URL-encoded form data
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30
            )

            _LOGGER.debug("Token refresh response status: %s", response.status_code)

            if response.status_code != 200:
                _LOGGER.error("Token refresh failed with status %s: %s",
                            response.status_code, response.text)
                return False

            token_data = response.json()
            _LOGGER.debug("Token refresh response data keys: %s", token_data.keys())

            # Extract new tokens
            new_access_token = token_data.get("access_token")
            new_id_token = token_data.get("id_token")
            new_refresh_token = token_data.get("refresh_token")

            if not new_access_token or not new_id_token:
                _LOGGER.error("Token refresh response missing tokens")
                return False

            # Add "Bearer " prefix if not present
            if not new_access_token.startswith("Bearer "):
                new_access_token = f"Bearer {new_access_token}"

            # Update tokens
            self._access_token = new_access_token
            self._id_token = new_id_token
            if new_refresh_token:
                self._refresh_token = new_refresh_token

            self._update_session_headers()

            # Notify callback if set
            if self._token_update_callback:
                _LOGGER.info("Calling token update callback to persist new tokens")
                self._token_update_callback(
                    new_access_token,
                    new_id_token,
                    new_refresh_token or self._refresh_token
                )

            _LOGGER.info("Successfully refreshed tokens")
            return True

        except Exception as e:
            _LOGGER.exception("Error refreshing tokens: %s", e)
            return False

    def _make_graphql_request(self, query: str, variables: Dict[str, Any], retry_on_401: bool = True) -> Dict[str, Any]:
        """Make a GraphQL request

        Args:
            query: GraphQL query string
            variables: Query variables
            retry_on_401: If True, automatically retry with token refresh on 401 errors

        Returns:
            GraphQL response data
        """
        if not self._access_token or not self._id_token:
            raise OVOAuthenticationError("Not authenticated")

        payload = {
            "query": query,
            "variables": variables
        }

        try:
            response = self.session.post(
                self.API_URL,
                json=payload,
                timeout=30
            )

            if response.status_code == 401:
                # Try to refresh tokens and retry once
                if retry_on_401 and self._refresh_token:
                    _LOGGER.info("Received 401, attempting token refresh...")
                    if self.refresh_tokens():
                        _LOGGER.info("Token refresh successful, retrying request...")
                        return self._make_graphql_request(query, variables, retry_on_401=False)
                    else:
                        _LOGGER.error("Token refresh failed")

                raise OVOTokenExpiredError("Access tokens expired and refresh failed")

            if response.status_code != 200:
                raise OVOAPIError(
                    f"API request failed with status {response.status_code}"
                )

            result = response.json()

            if "errors" in result:
                error_msg = "; ".join([e.get("message", str(e)) for e in result["errors"]])
                raise OVOAPIError(f"GraphQL errors: {error_msg}")

            return result.get("data", {})

        except requests.RequestException as e:
            raise OVOAPIError(f"Network error: {e}")

    def get_today_data(self) -> Dict[str, List[Dict]]:
        """Get today's hourly energy data"""
        if not self.account_id:
            raise ValueError("account_id must be set")

        today = datetime.now().strftime("%Y-%m-%d")

        query = """
        query GetHourlyData($input: GetHourlyDataInput!) {
          GetHourlyData(input: $input) {
            solar {
              periodFrom
              periodTo
              consumption
              readType
              charge {
                value
                type
              }
            }
            export {
              periodFrom
              periodTo
              consumption
              readType
              charge {
                value
                type
              }
              rates {
                type
                charge {
                  value
                  type
                }
                consumption
                percentOfTotal
              }
            }
            savings {
              periodFrom
              periodTo
              amount {
                value
                type
              }
              description
            }
          }
        }
        """

        variables = {
            "input": {
                "accountId": self.account_id,
                "dateRange": {
                    "startDate": today,
                    "endDate": today
                }
            }
        }

        result = self._make_graphql_request(query, variables)
        return result.get("GetHourlyData", {})

    def get_interval_data(self) -> Dict[str, Any]:
        """Get daily/monthly/yearly interval data

        Returns aggregated data for daily, monthly, and yearly periods.
        Useful for getting month-to-date and historical monthly totals.
        """
        if not self.account_id:
            raise ValueError("account_id must be set")

        query = """
        query GetIntervalData($input: GetIntervalDataInput!) {
          GetIntervalData(input: $input) {
            daily {
              solar {
                periodFrom
                periodTo
                consumption
                readType
                charge {
                  value
                  type
                }
              }
              export {
                periodFrom
                periodTo
                consumption
                readType
                charge {
                  value
                  type
                }
                rates {
                  type
                  charge {
                    value
                    type
                  }
                  consumption
                  percentOfTotal
                }
              }
              savings {
                periodFrom
                periodTo
                amount {
                  value
                  type
                }
                description
              }
            }
            monthly {
              solar {
                periodFrom
                periodTo
                consumption
                readType
                charge {
                  value
                  type
                }
              }
              export {
                periodFrom
                periodTo
                consumption
                readType
                charge {
                  value
                  type
                }
                rates {
                  type
                  charge {
                    value
                    type
                  }
                  consumption
                  percentOfTotal
                }
              }
              savings {
                periodFrom
                periodTo
                amount {
                  value
                  type
                }
                description
              }
            }
            yearly {
              solar {
                periodFrom
                periodTo
                consumption
                readType
                charge {
                  value
                  type
                }
              }
              export {
                periodFrom
                periodTo
                consumption
                readType
                charge {
                  value
                  type
                }
                rates {
                  type
                  charge {
                    value
                    type
                  }
                  consumption
                  percentOfTotal
                }
              }
              savings {
                periodFrom
                periodTo
                amount {
                  value
                  type
                }
                description
              }
            }
          }
        }
        """

        variables = {
            "input": {
                "accountId": self.account_id
            }
        }

        result = self._make_graphql_request(query, variables)
        return result.get("GetIntervalData", {})

    def close(self):
        """Clean up resources"""
        self.session.close()
