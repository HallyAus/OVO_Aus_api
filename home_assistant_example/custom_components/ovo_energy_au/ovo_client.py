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

    def __init__(self, access_token: Optional[str] = None,
                 id_token: Optional[str] = None,
                 account_id: Optional[str] = None):
        """Initialize the client"""
        self._access_token = access_token
        self._id_token = id_token
        self.account_id = account_id

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

    def set_tokens(self, access_token: str, id_token: str):
        """Set authentication tokens"""
        self._access_token = access_token
        self._id_token = id_token
        self._update_session_headers()

    def _make_graphql_request(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Make a GraphQL request"""
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
                raise OVOTokenExpiredError("Access tokens expired")

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
          getHourlyData(input: $input) {
            solar {
              periodFrom
              periodTo
              consumption
              readType
              charge {
                amount
                currency
              }
            }
            export {
              periodFrom
              periodTo
              consumption
              readType
              charge {
                amount
                currency
              }
            }
            savings {
              periodFrom
              periodTo
              consumption
              readType
              charge {
                amount
                currency
              }
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
        return result.get("getHourlyData", {})

    def close(self):
        """Clean up resources"""
        self.session.close()
