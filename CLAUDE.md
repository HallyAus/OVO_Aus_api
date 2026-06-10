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

## Release Process (MANDATORY — HACS only distributes tagged releases)
HACS resolves the installable version from the **latest GitHub release tag**, not
from main. A version bump without a release is invisible to users. Whenever the
version changes, ALWAYS do all of the following in the same session:

1. Bump the version in **four** places (they must agree):
   - `custom_components/ovo_energy_au/manifest.json` ("version")
   - `pyproject.toml` ([project] version)
   - `README.md` version badge
   - `info.md` version badge
2. Add a `CHANGELOG.md` entry for the new version (Keep a Changelog format)
3. Run `git fetch origin` and rebase before committing — remote main moves via
   cloud-agent PRs between local sessions
4. Commit and push to main
5. Create the GitHub release: `gh release create vX.Y.Z --target main --title "vX.Y.Z" --notes-file <notes>`
   - Release notes start with the referral support block (see release.yml for the template),
     then the changelog highlights
   - Tag format is `v` + semver (e.g. `v4.2.0`)
6. Attach the manual-install zip: `Compress-Archive custom_components\ovo_energy_au ovo_energy_au.zip`
   then `gh release upload vX.Y.Z ovo_energy_au.zip`
   - The `release.yml` workflow normally does steps 5-6 on tag push, but do it
     manually with `gh` whenever GitHub Actions is unavailable (e.g. billing lock)
7. Verify: `gh release list` must show the new tag as **Latest**

## Branding (logos/icons in HA and HACS)
HA and HACS load icons exclusively from https://github.com/home-assistant/brands
(`custom_integrations/ovo_energy_au/`), NOT from this repo. The PNGs in this repo
(`icon.png`, `icon@2x.png`, `brand/`) are only sources for that PR. If the icon
ever changes, a new PR to home-assistant/brands is required (icon.png must be
exactly 256x256, icon@2x.png 512x512, transparent background, trimmed).
