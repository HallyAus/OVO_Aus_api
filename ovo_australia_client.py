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
import hashlib
import secrets
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from threading import Timer
from urllib.parse import urlparse, parse_qs, urlencode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# PKCE Helper Functions
def _generate_code_verifier() -> str:
    """
    Generate a code verifier for PKCE flow

    Returns a URL-safe base64-encoded random string (43-128 characters)
    """
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8')
    # Remove padding
    return code_verifier.rstrip('=')


def _generate_code_challenge(code_verifier: str) -> str:
    """
    Generate a code challenge from the code verifier for PKCE flow

    Uses SHA256 hashing method

    Args:
        code_verifier: The code verifier string

    Returns:
        URL-safe base64-encoded SHA256 hash of the verifier
    """
    code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8')
    # Remove padding
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
        Authenticate with OVO Energy Australia using OAuth 2.0

        This method attempts multiple authentication strategies:
        1. Resource Owner Password Credentials (ROPC) grant
        2. Password realm grant (Auth0 specific)
        3. Database connection authentication

        Args:
            username: OVO account email
            password: OVO account password

        Returns:
            True if authentication successful

        Raises:
            OVOAuthenticationError: If authentication fails
        """
        logger.info(f"Attempting authentication for user: {username}")

        # Try multiple authentication strategies
        strategies = [
            self._auth_ropc,
            self._auth_password_realm,
            self._auth_database_connection
        ]

        for strategy in strategies:
            try:
                result = strategy(username, password)
                if result:
                    logger.info("Authentication successful!")
                    self._schedule_token_refresh()
                    return True
            except Exception as e:
                logger.debug(f"Strategy {strategy.__name__} failed: {e}")
                continue

        # If all strategies failed
        raise OVOAuthenticationError(
            "Authentication failed. Please verify your credentials. "
            "If the issue persists, you may need to use set_tokens() with "
            "manually extracted tokens from the browser."
        )

    def _auth_ropc(self, username: str, password: str) -> bool:
        """
        Try Resource Owner Password Credentials (ROPC) grant

        Args:
            username: User email
            password: User password

        Returns:
            True if successful, False otherwise
        """
        logger.debug("Trying ROPC grant")

        token_url = f"{self.AUTH0_DOMAIN}/oauth/token"

        payload = {
            "grant_type": "password",
            "username": username,
            "password": password,
            "client_id": self.CLIENT_ID,
            "scope": "openid profile email offline_access",
            "audience": "https://api.ovoenergy.com.au"
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

            logger.debug(f"ROPC failed with status {response.status_code}: {response.text}")
            return False

        except Exception as e:
            logger.debug(f"ROPC exception: {e}")
            return False

    def _auth_password_realm(self, username: str, password: str) -> bool:
        """
        Try password realm grant (Auth0 specific)

        Args:
            username: User email
            password: User password

        Returns:
            True if successful, False otherwise
        """
        logger.debug("Trying password realm grant")

        token_url = f"{self.AUTH0_DOMAIN}/oauth/token"

        payload = {
            "grant_type": "http://auth0.com/oauth/grant-type/password-realm",
            "username": username,
            "password": password,
            "client_id": self.CLIENT_ID,
            "realm": "Username-Password-Authentication",
            "scope": "openid profile email offline_access"
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

            logger.debug(f"Password realm failed with status {response.status_code}: {response.text}")
            return False

        except Exception as e:
            logger.debug(f"Password realm exception: {e}")
            return False

    def _auth_database_connection(self, username: str, password: str) -> bool:
        """
        Try Auth0 database connection login

        Args:
            username: User email
            password: User password

        Returns:
            True if successful, False otherwise
        """
        logger.debug("Trying database connection authentication")

        # First, get the database connection login token
        login_url = f"{self.AUTH0_DOMAIN}/usernamepassword/login"

        payload = {
            "client_id": self.CLIENT_ID,
            "username": username,
            "password": password,
            "credential_type": "http://auth0.com/oauth/grant-type/password-realm",
            "realm": "Username-Password-Authentication",
            "scope": "openid profile email offline_access"
        }

        try:
            session = requests.Session()
            response = session.post(
                login_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Auth0-Client": base64.b64encode(json.dumps({
                        "name": "auth0.js",
                        "version": "9.20.0"
                    }).encode()).decode()
                },
                timeout=30,
                allow_redirects=False
            )

            # Check if we got a redirect or token
            if response.status_code in [200, 302]:
                # Try to get tokens from the response
                try:
                    data = response.json()
                    if "access_token" in data or "id_token" in data:
                        return self._process_tokens(data)
                except:
                    pass

                # If we got redirected, try to follow the OAuth flow
                if response.status_code == 302 or "location" in response.headers:
                    location = response.headers.get("location", response.json().get("login_ticket"))
                    if location:
                        return self._complete_oauth_flow(session, location, username, password)

            logger.debug(f"Database connection failed with status {response.status_code}")
            return False

        except Exception as e:
            logger.debug(f"Database connection exception: {e}")
            return False

    def _complete_oauth_flow(self, session: requests.Session, state_or_ticket: str,
                            username: str, password: str) -> bool:
        """
        Complete the OAuth flow after initial login

        Args:
            session: Requests session with cookies
            state_or_ticket: State parameter or login ticket
            username: User email
            password: User password

        Returns:
            True if successful, False otherwise
        """
        logger.debug("Attempting to complete OAuth flow")

        # Generate PKCE parameters
        code_verifier = _generate_code_verifier()
        code_challenge = _generate_code_challenge(code_verifier)

        # Build authorization URL
        auth_params = {
            "client_id": self.CLIENT_ID,
            "response_type": "code",
            "redirect_uri": "https://my.ovoenergy.com.au/login/callback",
            "scope": "openid profile email offline_access",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": secrets.token_urlsafe(32)
        }

        try:
            # Try to get authorization code
            auth_url = f"{self.AUTH0_DOMAIN}/authorize?{urlencode(auth_params)}"
            response = session.get(auth_url, allow_redirects=True, timeout=30)

            # Look for authorization code in redirects
            for resp in [response] + list(getattr(response, 'history', [])):
                if "code=" in resp.url:
                    parsed = urlparse(resp.url)
                    query_params = parse_qs(parsed.query)
                    if "code" in query_params:
                        auth_code = query_params["code"][0]
                        return self._exchange_code_for_tokens(auth_code, code_verifier)

            logger.debug("No authorization code found in OAuth flow")
            return False

        except Exception as e:
            logger.debug(f"OAuth flow completion exception: {e}")
            return False

    def _exchange_code_for_tokens(self, auth_code: str, code_verifier: str) -> bool:
        """
        Exchange authorization code for tokens

        Args:
            auth_code: Authorization code from OAuth flow
            code_verifier: PKCE code verifier

        Returns:
            True if successful, False otherwise
        """
        logger.debug("Exchanging authorization code for tokens")

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

            logger.debug(f"Token exchange failed with status {response.status_code}: {response.text}")
            return False

        except Exception as e:
            logger.debug(f"Token exchange exception: {e}")
            return False

    def _process_tokens(self, tokens: Dict[str, Any]) -> bool:
        """
        Process and store authentication tokens

        Args:
            tokens: Dictionary containing access_token, id_token, and optionally refresh_token

        Returns:
            True if tokens were successfully processed
        """
        access_token = tokens.get("access_token")
        id_token = tokens.get("id_token")
        refresh_token = tokens.get("refresh_token")

        if not access_token or not id_token:
            logger.error("Missing required tokens in response")
            return False

        # Store tokens (add "Bearer " prefix to access_token if not present)
        if not access_token.startswith("Bearer "):
            access_token = f"Bearer {access_token}"

        self._access_token = access_token
        self._id_token = id_token
        self._refresh_token = refresh_token

        self._update_session_headers()

        # Try to extract account_id from ID token if not already set
        if not self.account_id:
            self.account_id = self._extract_account_id_from_token(id_token)

        logger.info("Tokens successfully processed and stored")
        return True

    def _extract_account_id_from_token(self, id_token: str) -> Optional[str]:
        """
        Attempt to extract account_id from ID token

        Note: This may not always work as the account_id might not be in the token.
        If extraction fails, account_id must be set manually.

        Args:
            id_token: JWT ID token

        Returns:
            Account ID if found, None otherwise
        """
        try:
            # Decode JWT without verification (we just need to read the payload)
            parts = id_token.split('.')
            if len(parts) != 3:
                return None

            # Add padding if needed
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding

            # Decode base64
            decoded = base64.urlsafe_b64decode(payload)
            payload_data = json.loads(decoded)

            # Look for account_id in various possible fields
            for field in ['account_id', 'accountId', 'sub', 'user_id']:
                if field in payload_data:
                    value = str(payload_data[field])
                    # Check if it looks like an account ID (numeric)
                    if value.isdigit():
                        logger.info(f"Extracted account_id from token: {value}")
                        return value

            logger.debug("Could not find account_id in ID token")
            return None

        except Exception as e:
            logger.debug(f"Failed to extract account_id from token: {e}")
            return None

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

        Uses the refresh token to obtain new access and ID tokens.
        Automatically re-schedules the next refresh.

        Raises:
            OVOTokenExpiredError: If refresh fails
        """
        if not self._refresh_token:
            logger.error("Cannot refresh tokens: no refresh_token available")
            raise OVOTokenExpiredError("Tokens expired and no refresh token available")

        logger.info("Refreshing tokens...")

        token_url = f"{self.AUTH0_DOMAIN}/oauth/token"

        payload = {
            "grant_type": "refresh_token",
            "client_id": self.CLIENT_ID,
            "refresh_token": self._refresh_token
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

                # Update tokens
                access_token = tokens.get("access_token")
                id_token = tokens.get("id_token")
                refresh_token = tokens.get("refresh_token")  # May get a new refresh token

                if not access_token or not id_token:
                    raise OVOTokenExpiredError("Token refresh response missing required tokens")

                # Add Bearer prefix if needed
                if not access_token.startswith("Bearer "):
                    access_token = f"Bearer {access_token}"

                self._access_token = access_token
                self._id_token = id_token

                # Update refresh token if a new one was provided
                if refresh_token:
                    self._refresh_token = refresh_token

                self._update_session_headers()

                logger.info("Tokens successfully refreshed")

                # Schedule next refresh
                self._schedule_token_refresh()

            else:
                error_msg = f"Token refresh failed with status {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise OVOTokenExpiredError(error_msg)

        except requests.RequestException as e:
            error_msg = f"Network error during token refresh: {e}"
            logger.error(error_msg)
            raise OVOTokenExpiredError(error_msg)

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

    This demonstrates both OAuth authentication and manual token usage.
    """
    print("OVO Energy Australia API Client")
    print("=" * 50)
    print()

    # Choose authentication method
    print("Authentication Methods:")
    print("1. OAuth Login (username/password)")
    print("2. Manual Tokens (from browser)")
    print()
    choice = input("Choose method (1 or 2): ").strip()

    client = None

    if choice == "1":
        # OAuth authentication
        print("\nOAuth Authentication")
        print("-" * 50)
        username = input("Enter email: ").strip()
        password = input("Enter password: ").strip()
        account_id = input("Enter account_id (if known, or press Enter to skip): ").strip() or None

        client = OVOEnergyAU(account_id=account_id)

        try:
            print("\nAuthenticating...")
            client.authenticate(username, password)
            print("✓ Authentication successful!")

            # If account_id wasn't provided, we should fetch it
            # (This would require implementing a getAccountDetails query)
            if not client.account_id:
                account_id = input("Enter your account_id: ").strip()
                client.account_id = account_id

        except OVOAuthenticationError as e:
            print(f"\n✗ Authentication failed: {e}")
            print("\nFalling back to manual token entry...")
            choice = "2"  # Fall through to manual token entry

    if choice == "2":
        # Manual token authentication
        print("\nManual Token Authentication")
        print("-" * 50)
        print("See QUICK_START.md for instructions on extracting tokens from browser.")
        print()

        access_token = input("Enter access_token (starts with 'Bearer '): ").strip()
        id_token = input("Enter id_token (JWT): ").strip()
        account_id = input("Enter account_id: ").strip()

        if not client:
            client = OVOEnergyAU(account_id=account_id)
        client.set_tokens(access_token, id_token)
        print("✓ Tokens set successfully!")

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
