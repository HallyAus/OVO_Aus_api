"""Constants for OVO Energy Australia integration."""

# Domain
DOMAIN = "ovo_energy_au"

# Configuration keys
CONF_ACCESS_TOKEN = "access_token"
CONF_ID_TOKEN = "id_token"
CONF_ACCOUNT_ID = "account_id"

# Default values
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes (matches token expiry)

# Sensor types
SENSOR_SOLAR_CURRENT = "solar_current"
SENSOR_EXPORT_CURRENT = "export_current"
SENSOR_SOLAR_TODAY = "solar_today"
SENSOR_EXPORT_TODAY = "export_today"
SENSOR_SAVINGS_TODAY = "savings_today"

# Units
UNIT_KWH = "kWh"
UNIT_CURRENCY = "AUD"
