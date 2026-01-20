"""Constants for OVO Energy Australia integration."""

# Domain
DOMAIN = "ovo_energy_au"

# Configuration keys
CONF_ACCESS_TOKEN = "access_token"
CONF_ID_TOKEN = "id_token"
CONF_ACCOUNT_ID = "account_id"
CONF_REFRESH_TOKEN = "refresh_token"

# Default values
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes (matches token expiry)

# Sensor types
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
