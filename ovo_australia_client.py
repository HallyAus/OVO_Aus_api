#!/usr/bin/env python3
"""
OVO Energy Australia API Client

A Python client for interacting with OVO Energy Australia's GraphQL API.
This client handles authentication, token management, and data retrieval.

Author: Reverse-engineered by Claude (Sonnet 4.5) + Daniel
Date: January 2026
"""

import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from threading import Timer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    """
    OVO Energy Australia API Client

    This client provides access to OVO Energy Australia's GraphQL API,
    including energy usage data, solar generation, and export information.

    Authentication uses Auth0 OAuth 2.0 with dual JWT tokens:
    - access_token: Used in Authorization header
    - id_token: Used in myovo-id-token header

    Tokens expire after 5 minutes and must be refreshed.
    """

    # API Configuration
    API_URL = "https://my.ovoenergy.com.au/graphql"
    AUTH0_DOMAIN = "https://login.ovoenergy.com.au"
    CLIENT_ID = "5JHnPn71qgV3LmF3I3xX0KvfRBdROVhR"

    # Token expiry configuration
    TOKEN_EXPIRY_SECONDS = 300  # 5 minutes
    TOKEN_REFRESH_BUFFER = 60   # Refresh 1 minute before expiry

    def __init__(self, access_token: Optional[str] = None,
                 id_token: Optional[str] = None,
                 account_id: Optional[str] = None):
        """
        Initialize the OVO Energy Australia client

        Args:
            access_token: JWT access token (if already obtained)
            id_token: JWT ID token (if already obtained)
            account_id: OVO account ID
        """
        self._access_token = access_token
        self._id_token = id_token
        self.account_id = account_id
        self._token_refresh_timer = None
        self._refresh_token = None

        # Initialize session with required headers
        self.session = requests.Session()
        self._update_session_headers()

    def _update_session_headers(self):
        """Update session headers with current tokens"""
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Origin': 'https://my.ovoenergy.com.au',
            'Referer': 'https://my.ovoenergy.com.au/usage',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        if self._access_token:
            self.session.headers['authorization'] = self._access_token
        if self._id_token:
            self.session.headers['myovo-id-token'] = self._id_token

    def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate with OVO Energy Australia

        CRITICAL: This method is NOT yet implemented!

        TODO: Implement full OAuth 2.0 PKCE flow:
        1. POST to /usernamepassword/login
        2. GET /authorize/resume?state=...
        3. POST /oauth/token
        4. Extract access_token and id_token
        5. Schedule token refresh

        Args:
            username: OVO account email
            password: OVO account password

        Returns:
            True if authentication successful

        Raises:
            OVOAuthenticationError: If authentication fails
            NotImplementedError: Currently not implemented
        """
        raise NotImplementedError(
            "OAuth 2.0 authentication not yet implemented. "
            "Please use set_tokens() method with manually obtained tokens. "
            "See QUICK_START.md for instructions on extracting tokens from browser."
        )

    def set_tokens(self, access_token: str, id_token: str,
                   refresh_token: Optional[str] = None):
        """
        Manually set authentication tokens

        Use this method when tokens are obtained externally (e.g., from browser).
        This is a temporary solution until OAuth flow is implemented.

        Args:
            access_token: JWT access token
            id_token: JWT ID token
            refresh_token: Optional refresh token for automatic renewal
        """
        self._access_token = access_token
        self._id_token = id_token
        self._refresh_token = refresh_token
        self._update_session_headers()

        # Schedule token refresh if refresh_token is available
        if refresh_token:
            self._schedule_token_refresh()
        else:
            logger.warning(
                "No refresh token provided. Tokens will expire in ~5 minutes. "
                "You'll need to manually refresh tokens."
            )

    def _schedule_token_refresh(self):
        """Schedule automatic token refresh before expiry"""
        if self._token_refresh_timer:
            self._token_refresh_timer.cancel()

        # Refresh 1 minute before expiry (4 minutes)
        refresh_delay = self.TOKEN_EXPIRY_SECONDS - self.TOKEN_REFRESH_BUFFER
        self._token_refresh_timer = Timer(refresh_delay, self._refresh_tokens)
        self._token_refresh_timer.daemon = True
        self._token_refresh_timer.start()

        logger.info(f"Token refresh scheduled in {refresh_delay} seconds")

    def _refresh_tokens(self):
        """
        Refresh expired tokens using refresh_token

        TODO: Implement token refresh logic:
        1. POST to /oauth/token with refresh_token
        2. Update _access_token and _id_token
        3. Update session headers
        4. Re-schedule next refresh

        Raises:
            OVOTokenExpiredError: If refresh fails
            NotImplementedError: Currently not implemented
        """
        if not self._refresh_token:
            logger.error("Cannot refresh tokens: no refresh_token available")
            raise OVOTokenExpiredError("Tokens expired and no refresh token available")

        logger.warning("Token refresh not yet implemented")
        raise NotImplementedError("Token refresh not yet implemented")

    def _make_graphql_request(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a GraphQL request to the OVO API

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            GraphQL response data

        Raises:
            OVOTokenExpiredError: If tokens are expired
            OVOAPIError: If API request fails
        """
        if not self._access_token or not self._id_token:
            raise OVOAuthenticationError(
                "Not authenticated. Call authenticate() or set_tokens() first."
            )

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

            # Check for authentication errors
            if response.status_code == 401:
                raise OVOTokenExpiredError(
                    "Access tokens expired. Please re-authenticate."
                )

            # Check for other errors
            if response.status_code != 200:
                raise OVOAPIError(
                    f"API request failed with status {response.status_code}: {response.text}"
                )

            result = response.json()

            # Check for GraphQL errors
            if "errors" in result:
                error_msg = "; ".join([e.get("message", str(e)) for e in result["errors"]])
                raise OVOAPIError(f"GraphQL errors: {error_msg}")

            return result.get("data", {})

        except requests.RequestException as e:
            raise OVOAPIError(f"Network error during API request: {e}")

    def get_hourly_data(self, start_date: datetime, end_date: datetime) -> Dict[str, List[Dict]]:
        """
        Retrieve hourly energy data for a date range

        This fetches solar generation, grid export, and cost savings data
        at hourly granularity.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            Dictionary containing:
                - solar: List of solar generation data points
                - export: List of export to grid data points
                - savings: List of cost savings data points

            Each data point has:
                - periodFrom: ISO datetime string
                - periodTo: ISO datetime string
                - consumption: Float (kWh)
                - readType: "ACTUAL" or "ESTIMATED"
                - charge: Optional cost object

        Raises:
            ValueError: If account_id not set
            OVOAPIError: If API request fails
        """
        if not self.account_id:
            raise ValueError("account_id must be set before fetching data")

        # Format dates as YYYY-MM-DD
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # GraphQL query for hourly data
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
                    "startDate": start_str,
                    "endDate": end_str
                }
            }
        }

        logger.info(f"Fetching hourly data from {start_str} to {end_str}")

        result = self._make_graphql_request(query, variables)
        return result.get("getHourlyData", {})

    def get_today_data(self) -> Dict[str, List[Dict]]:
        """
        Convenience method to get today's hourly data

        Returns:
            Hourly data for today
        """
        today = datetime.now()
        return self.get_hourly_data(today, today)

    def get_yesterday_data(self) -> Dict[str, List[Dict]]:
        """
        Convenience method to get yesterday's hourly data

        Returns:
            Hourly data for yesterday
        """
        yesterday = datetime.now() - timedelta(days=1)
        return self.get_hourly_data(yesterday, yesterday)

    def get_last_7_days(self) -> Dict[str, List[Dict]]:
        """
        Convenience method to get last 7 days of hourly data

        Returns:
            Hourly data for the last 7 days
        """
        end = datetime.now()
        start = end - timedelta(days=7)
        return self.get_hourly_data(start, end)

    def get_current_hour_solar(self) -> Optional[float]:
        """
        Get solar generation for the current hour

        Returns:
            Solar generation in kWh, or None if no data available
        """
        data = self.get_today_data()
        solar_data = data.get("solar", [])

        if not solar_data:
            return None

        # Get the most recent data point
        latest = solar_data[-1]
        return latest.get("consumption")

    def close(self):
        """Clean up resources"""
        if self._token_refresh_timer:
            self._token_refresh_timer.cancel()
        self.session.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


def main():
    """
    Example usage of the OVO Energy Australia client

    This demonstrates how to use the client with manually obtained tokens.
    """
    print("OVO Energy Australia API Client")
    print("=" * 50)
    print()

    # Get tokens from user
    print("You need to provide tokens manually until OAuth is implemented.")
    print("See QUICK_START.md for instructions on extracting tokens from browser.")
    print()

    access_token = input("Enter access_token (starts with 'Bearer '): ").strip()
    id_token = input("Enter id_token (JWT): ").strip()
    account_id = input("Enter account_id: ").strip()

    # Create client and set tokens
    client = OVOEnergyAU(account_id=account_id)
    client.set_tokens(access_token, id_token)

    try:
        # Fetch today's data
        print("\nFetching today's energy data...")
        data = client.get_today_data()

        # Display results
        print("\n" + "=" * 50)
        print("SOLAR GENERATION")
        print("=" * 50)
        solar_data = data.get("solar", [])
        if solar_data:
            for point in solar_data[-5:]:  # Show last 5 hours
                time = point.get("periodFrom", "")[:16]  # Truncate to minute
                consumption = point.get("consumption", 0)
                read_type = point.get("readType", "")
                print(f"{time}: {consumption:.2f} kWh ({read_type})")
        else:
            print("No solar data available")

        print("\n" + "=" * 50)
        print("EXPORT TO GRID")
        print("=" * 50)
        export_data = data.get("export", [])
        if export_data:
            for point in export_data[-5:]:  # Show last 5 hours
                time = point.get("periodFrom", "")[:16]
                consumption = point.get("consumption", 0)
                read_type = point.get("readType", "")
                print(f"{time}: {consumption:.2f} kWh ({read_type})")
        else:
            print("No export data available")

        print("\n" + "=" * 50)
        print("COST SAVINGS")
        print("=" * 50)
        savings_data = data.get("savings", [])
        if savings_data:
            total_savings = sum(
                point.get("charge", {}).get("amount", 0)
                for point in savings_data
            )
            print(f"Total savings today: ${total_savings:.2f}")
        else:
            print("No savings data available")

    except OVOAuthenticationError as e:
        print(f"\nAuthentication Error: {e}")
    except OVOAPIError as e:
        print(f"\nAPI Error: {e}")
    except Exception as e:
        print(f"\nUnexpected Error: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
