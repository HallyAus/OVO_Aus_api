"""Constants for the OVO Energy Australia integration."""

from datetime import timedelta

# Integration domain
DOMAIN = "ovo_energy_au"

# Configuration and options
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

# Default rates (AUD per kWh) - users can customize these
DEFAULT_RATES = {
    PLAN_FREE_3: {
        "peak": 0.35,
        "shoulder": 0.25,
        "off_peak": 0.18,
        "free_start": 11,  # 11:00
        "free_end": 14,    # 14:00
    },
    PLAN_EV: {
        "peak": 0.35,
        "shoulder": 0.25,
        "off_peak": 0.18,
        "ev": 0.06,
        "ev_start": 0,     # 00:00
        "ev_end": 6,       # 06:00
        "free_start": 11,  # Some EV plans include free period
        "free_end": 14,
    },
    PLAN_BASIC: {
        "peak": 0.35,
        "shoulder": 0.25,
        "off_peak": 0.18,
    },
    PLAN_ONE: {
        "flat": 0.28,      # Single rate all day
    },
}

# Time-of-Use periods (24-hour format)
# These are typical NSW/QLD distributor TOU windows
TOU_PERIODS = {
    "peak": {
        "weekday_start": 14,  # 14:00 (2pm)
        "weekday_end": 21,    # 21:00 (9pm) - exclusive
        "applies_weekend": False,
    },
    "off_peak": {
        "start": 22,  # 22:00 (10pm)
        "end": 7,     # 07:00 (7am)
        "applies_weekend": True,
    },
    # Shoulder is everything else
}

# Auth0 / OAuth2 constants
AUTH_BASE_URL = "https://login.ovoenergy.com.au"
API_BASE_URL = "https://my.ovoenergy.com.au"
GRAPHQL_URL = f"{API_BASE_URL}/graphql"

OAUTH_CLIENT_ID = "5JHnPn71qgV3LmF3I3xX0KvfRBdROVhR"
OAUTH_AUTHORIZE_URL = f"{AUTH_BASE_URL}/authorize"
OAUTH_TOKEN_URL = f"{AUTH_BASE_URL}/oauth/token"
OAUTH_LOGIN_URL = f"{AUTH_BASE_URL}/usernamepassword/login"
OAUTH_SCOPES = ["openid", "profile", "email", "offline_access"]
OAUTH_AUDIENCE = f"{AUTH_BASE_URL}/api"
OAUTH_CONNECTION = "prod-myovo-auth"  # Auth0 database connection name
OAUTH_REDIRECT_URI = f"{API_BASE_URL}?login=oea"

# Update intervals
# Poll daily at 6am since data is only available for yesterday
UPDATE_INTERVAL = timedelta(hours=24)
UPDATE_HOUR = 6  # 6am daily
FAST_UPDATE_INTERVAL = timedelta(minutes=5)  # For manual refresh

# Hourly data settings
# Note: Hourly data now fetches only yesterday's data (the day before today)
# This ensures the sensor displays hourly consumption for the previous day
HOURLY_DATA_DAYS = 1  # DEPRECATED: Now always fetches yesterday only

# Sensor identifiers
SENSOR_SOLAR_CURRENT = "solar_current"
SENSOR_EXPORT_CURRENT = "export_current"
SENSOR_SOLAR_TODAY = "solar_today"
SENSOR_EXPORT_TODAY = "export_today"
SENSOR_SAVINGS_TODAY = "savings_today"
SENSOR_SOLAR_THIS_MONTH = "solar_this_month"
SENSOR_SOLAR_LAST_MONTH = "solar_last_month"
SENSOR_EXPORT_THIS_MONTH = "export_this_month"
SENSOR_EXPORT_LAST_MONTH = "export_last_month"
SENSOR_SAVINGS_THIS_MONTH = "savings_this_month"
SENSOR_SAVINGS_LAST_MONTH = "savings_last_month"

# Units
UNIT_KWH = "kWh"
UNIT_CURRENCY = "AUD"

# Sensor types
SENSOR_TYPES = {
    "solar_consumption": {
        "name": "Solar Consumption",
        "unit": "kWh",
        "icon": "mdi:solar-power",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    "export_consumption": {
        "name": "Export Consumption",
        "unit": "kWh",
        "icon": "mdi:transmission-tower-export",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    "solar_charge": {
        "name": "Solar Charge",
        "unit": "$",
        "icon": "mdi:currency-usd",
        "device_class": "monetary",
        "state_class": "total",
    },
    "export_charge": {
        "name": "Export Charge",
        "unit": "$",
        "icon": "mdi:currency-usd",
        "device_class": "monetary",
        "state_class": "total",
    },
}

# GraphQL queries
GET_CONTACT_INFO_QUERY = """
query GetContactInfo($input: GetContactInfoInput!) {
  GetContactInfo(input: $input) {
    accounts {
      id
      number
      customerId
      customerOrientatedBalance
      closed
      system
      hasSolar
      supplyAddress {
        buildingName
        buildingName2
        lotNumber
        flatType
        flatNumber
        floorType
        floorNumber
        houseNumber
        houseNumber2
        houseSuffix
        houseSuffix2
        streetSuffix
        streetName
        streetType
        suburb
        state
        postcode
        countryCode
        country
        addressType
        __typename
      }
      __typename
    }
    __typename
  }
}
"""

GET_INTERVAL_DATA_QUERY = """
query GetIntervalData($input: GetIntervalDataInput!) {
  GetIntervalData(input: $input) {
    daily {
      ...UsageV2DataParts
      __typename
    }
    monthly {
      ...UsageV2DataParts
      __typename
    }
    yearly {
      ...UsageV2DataParts
      __typename
    }
    __typename
  }
}

fragment UsageV2DataParts on UsageV2Data {
  solar {
    periodFrom
    periodTo
    consumption
    readType
    charge {
      value
      type
      __typename
    }
    __typename
  }
  export {
    periodFrom
    periodTo
    consumption
    readType
    charge {
      value
      type
      __typename
    }
    __typename
  }
  __typename
}
"""

GET_HOURLY_DATA_QUERY = """
query GetHourlyData($input: GetHourlyDataInput!) {
  GetHourlyData(input: $input) {
    ...UsageV2DataParts
    __typename
  }
}

fragment UsageV2DataParts on UsageV2Data {
  solar {
    periodFrom
    periodTo
    consumption
    readType
    charge {
      value
      type
      __typename
    }
    __typename
  }
  export {
    periodFrom
    periodTo
    consumption
    readType
    charge {
      value
      type
      __typename
    }
    __typename
  }
  __typename
}
"""

# Error messages
ERROR_AUTH_FAILED = "Authentication failed. Please check your credentials."
ERROR_CANNOT_CONNECT = "Cannot connect to OVO Energy API."
ERROR_INVALID_AUTH = "Invalid authentication."
ERROR_UNKNOWN = "Unknown error occurred."
