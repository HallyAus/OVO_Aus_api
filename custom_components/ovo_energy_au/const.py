"""Constants for the OVO Energy Australia integration."""

from datetime import timedelta

# Integration domain
DOMAIN = "ovo_energy_au"

# Configuration keys
CONF_ACCOUNT_ID = "account_id"
CONF_PLAN_TYPE = "plan_type"
CONF_PEAK_RATE = "peak_rate"
CONF_SHOULDER_RATE = "shoulder_rate"
CONF_OFF_PEAK_RATE = "off_peak_rate"
CONF_EV_RATE = "ev_rate"
CONF_FLAT_RATE = "flat_rate"

# Plan types
PLAN_FREE_3 = "free_3"
PLAN_EV = "ev"
PLAN_BASIC = "basic"
PLAN_ONE = "one"

PLAN_NAMES = {
    PLAN_FREE_3: "The Free 3 Plan",
    PLAN_EV: "The EV Plan",
    PLAN_BASIC: "The Basic Plan",
    PLAN_ONE: "The One Plan",
}

DEFAULT_RATES = {
    PLAN_FREE_3: {
        "peak": 0.35,
        "shoulder": 0.25,
        "off_peak": 0.18,
        "free_start": 11,
        "free_end": 14,
    },
    PLAN_EV: {
        "peak": 0.35,
        "shoulder": 0.25,
        "off_peak": 0.18,
        "ev": 0.06,
        "ev_start": 0,
        "ev_end": 6,
        "free_start": 11,
        "free_end": 14,
    },
    PLAN_BASIC: {
        "peak": 0.35,
        "shoulder": 0.25,
        "off_peak": 0.18,
    },
    PLAN_ONE: {
        "flat": 0.28,
    },
}

# Auth0 / OAuth2
AUTH_BASE_URL = "https://login.ovoenergy.com.au"
API_BASE_URL = "https://my.ovoenergy.com.au"
GRAPHQL_URL = f"{API_BASE_URL}/graphql"

OAUTH_CLIENT_ID = "5JHnPn71qgV3LmF3I3xX0KvfRBdROVhR"
OAUTH_AUTHORIZE_URL = f"{AUTH_BASE_URL}/authorize"
OAUTH_TOKEN_URL = f"{AUTH_BASE_URL}/oauth/token"
OAUTH_LOGIN_URL = f"{AUTH_BASE_URL}/usernamepassword/login"
OAUTH_SCOPES = ["openid", "profile", "email", "offline_access"]
OAUTH_AUDIENCE = f"{AUTH_BASE_URL}/api"
OAUTH_CONNECTION = "prod-myovo-auth"
OAUTH_REDIRECT_URI = f"{API_BASE_URL}?login=oea"

# Update intervals
FAST_UPDATE_INTERVAL = timedelta(minutes=5)

# Token refresh
TOKEN_REFRESH_BUFFER_PERCENT = 0.2
TOKEN_REFRESH_MAX_BUFFER_SECONDS = 120
TOKEN_REFRESH_MIN_BUFFER_SECONDS = 60

# Rate limiting
MIN_REQUEST_INTERVAL_SECONDS = 1.0
