"""
OVO Energy Australia API Client for Home Assistant

Simplified version of the main client for Home Assistant integration.
"""

import requests
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

_LOGGER = logging.getLogger(__name__)


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
            "refresh_token": self._refresh_token
        }

        try:
            _LOGGER.debug("Refreshing tokens...")
            response = self.session.post(token_url, data=payload, timeout=30)

            if response.status_code != 200:
                _LOGGER.error("Token refresh failed with status %s: %s",
                            response.status_code, response.text)
                return False

            token_data = response.json()

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

    def close(self):
        """Clean up resources"""
        self.session.close()
