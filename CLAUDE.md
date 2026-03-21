# OVO Energy Australia - Home Assistant Integration

## Project Overview
Custom Home Assistant integration for OVO Energy Australia. Fetches energy data via
OVO's GraphQL API (Auth0 OAuth2 + PKCE) and exposes 90+ sensors for solar, grid,
export, rate breakdowns, and analytics.

## Architecture
```
custom_components/ovo_energy_au/
├── __init__.py          # HA entry points (setup/unload)
├── api.py               # Async API client (OAuth2 + GraphQL)
├── config_flow.py       # HA UI config + options + reauth flows
├── coordinator.py       # DataUpdateCoordinator (data fetching)
├── const.py             # Domain, config keys, update intervals
├── models.py            # TypedDict/dataclass for data structures
├── sensor.py            # Sensor platform entry point + specialized classes
├── analytics/
│   ├── __init__.py      # Package exports
│   ├── interval.py      # Daily/monthly/yearly interval processing
│   ├── hourly.py        # Hourly data processing + TOU breakdown
│   └── insights.py      # Week comparison, projections, self-sufficiency
├── sensors/
│   ├── __init__.py      # Package marker
│   ├── base.py          # Base sensor classes + hourly data helpers
│   └── definitions.py   # Data-driven sensor definitions
├── graphql/
│   ├── __init__.py      # Package marker
│   └── queries.py       # All GraphQL query strings
├── manifest.json
├── services.yaml
├── strings.json
└── translations/en.json
tests/
├── __init__.py
├── conftest.py          # Shared fixtures + HA module mocking
├── test_analytics.py    # Analytics processing tests
├── test_models.py       # PlanConfig dataclass tests
├── test_sensor_definitions.py  # Sensor tuple structure + value_fn tests
├── test_hourly_helpers.py      # Timestamp parsing + hourly data filtering
└── test_edge_cases.py   # Null data, no solar, flat rate edge cases
```

## Key Commands
```bash
# Run tests
pytest tests/ -v

# Run a single test
pytest tests/test_analytics.py -v -k "test_name"

# Lint
ruff check custom_components/ovo_energy_au/

# Type check
mypy custom_components/ovo_energy_au/
```

## Conventions
- All monetary values in AUD (dollars, not cents). API returns cents -> divide by 100
- Timezone handling uses `zoneinfo.ZoneInfo("Australia/Sydney")` (aliased as `AU_TIMEZONE`)
  to correctly handle AEST/AEDT daylight saving transitions
- API charge types: PEAK, OFF_PEAK, SHOULDER, EV_OFFPEAK, FREE_3, OTHER, CREDIT, DEBIT
- CREDIT = solar export (return to grid), everything else = grid consumption
- Sensor unique_id format: `{account_id}_{sensor_key}`
- Device grouping via `device_category` string on each sensor

## API Authentication Flow
1. PKCE code_verifier/challenge generation
2. GET /authorize -> establish Auth0 session
3. POST /usernamepassword/login -> get HTML form with hidden fields
4. POST form_action -> follow redirects -> extract authorization code
5. POST /oauth/token -> exchange code for access/id/refresh tokens
6. Proactive refresh at 80% of token lifetime
