# Changelog

All notable changes to the OVO Energy Australia Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.1.0] - 2026-03-21

### New Sensors
- **Tariff Period Indicator** - Shows current rate period (EV Off-Peak / Super Off-Peak FREE / Standard) with live rate in c/kWh and next period change time
- **Plan Comparison & Recommendation** - Savings rating (Excellent/Good/Fair/Marginal), projected annual savings, recommendation text
- **EV Charging Tracker** - Monthly and yearly EV charging kWh and cost from rate breakdown data
- **Bill Estimator** - Month-to-date bill (grid + standing charge - solar credit), projected monthly bill, remaining estimate, daily average net cost

### New Features
- **HA Energy Dashboard** - Monthly solar/grid/export sensors now use TOTAL_INCREASING for native Energy Dashboard compatibility
- **Daily Savings Blueprint** - Automation blueprint sending daily notification with savings, solar, grid, cost
- **5 New Translations** - Simplified Chinese, Vietnamese, Greek, Italian, Arabic
- **GetUsageInfo API** - Fetches meter type, API timezone, last meter read
- **Account Balance sensor** - From customerOrientatedBalance in GetContactInfo

### Bug Fixes
- **CRITICAL: Added `savings` field to GraphQL fragment** - OVO Savings sensors were returning None because the query didn't request savings data
- **CRITICAL: Fixed potential UnboundLocalError** in tariff period sensor (elif -> else)
- **Fixed abs() on savings values** - Negative savings now correctly trigger "Consider switching plans" in plan comparison
- **Fixed months_included overcounting** - Was counting export entries, not unique months
- **Changed 3 frequent INFO logs to DEBUG** - Tokens, auth, product agreements no longer spam logs every 5 minutes

### Improvements
- Enriched Plan sensor with CL1 rate, demand charge, monthly/yearly standing charge calculations
- Health sensor shows meter type, API timezone, hasSolar, last meter read
- OVOEnergySensor base class now provides rich attributes for analytics sensors
- Dashboard YAML files rewritten with generic entity IDs and hourly charts
- New dedicated hourly data dashboard (dashboard_hourly.yaml)
- info.md (HACS page) completely rewritten with referral and feature overview

---

## [4.0.0] - 2026-03-20

### Breaking Changes
- Removed 72 individual per-hour sensors (data now available in hourly day sensor attributes)
- Entity names use relative labels ("1d Ago") instead of date stamps - may require dashboard updates
- Removed deprecated `home_assistant_example/` directory
- Removed standalone `ovo_australia_client.py`

### Architecture
- Complete modular restructure: split monolithic files into focused modules
- `__init__.py`: 1,322 → 82 lines (coordinator extracted to `coordinator.py`)
- `sensor.py`: 2,418 → ~500 lines (definitions extracted to `sensors/definitions.py`)
- `api.py`: unified `_graphql_request()` eliminates 120 lines of duplicated error handling
- `const.py`: 343 → 70 lines (GraphQL queries moved to `graphql/queries.py`)
- New `models.py` with TypedDict and dataclass definitions
- New `analytics/` package: `interval.py`, `hourly.py`, `insights.py`

### Bug Fixes (Critical)
- Fixed self-sufficiency score formula (was using total solar instead of self-consumed)
- Fixed daily data loss when both grid consumption and solar export exist on the same day
- Fixed `_process_period_latest` silently dropping either grid or export data
- Fixed OAuth2 URL parameters not being URL-encoded (spaces in scopes)
- Fixed entity count depending on first API response (now always creates 7 day sensors)

### Bug Fixes (High)
- Fixed hardcoded AEST timezone ignoring DST (now uses `ZoneInfo("Australia/Sydney")`)
- Fixed `_ensure_authenticated` falling through silently when both re-auth and refresh fail
- Fixed `OVODayRateSensor` reading from `last_3_days` instead of `all_daily_entries`
- Fixed peak 4-hour window double-counting from mixed solar+grid timeline
- Fixed heatmap double-counting hours with multiple rate entries
- Fixed `ev_usage_monthly` aliasing same dict as `ev_usage`
- Fixed `set_tokens` using truthiness check instead of `is not None`
- Fixed `refresh_tokens` not handling 401 status code
- Fixed `get_contact_info` accessing `_id_token` before authentication check

### New Features
- Added reauth flow (`async_step_reauth`) for automatic credential recovery
- Added integration health diagnostic sensor
- Added 401 retry logic with automatic token refresh
- Added rate limiter lock for concurrent request safety
- Added date format validation on hourly data requests
- Added CI/CD with GitHub Actions (lint, test, hassfest, HACS validation)

### Improvements
- Data-driven sensor definitions (add sensors by editing a list, not constructor calls)
- Sensor attributes restored for analytics, monthly breakdowns, and hourly data
- Rate breakdown computation cached per update cycle
- UTC-aware datetime throughout token management
- Token refresh buffer now applies minimum floor
- Unbounded daily entries capped at 90 days
- Raw API entries trimmed to needed fields (reduced memory)
- Accurate hour counting in rate aggregation
- Service registered once with multi-account support and proper cleanup
- Removed deprecated `async_reload_entry`
- Changed PII logging from INFO to DEBUG
- Fixed misleading "encrypted storage" claim in setup description
- Removed `aiohttp` from manifest requirements (HA core dependency)

### Testing
- Added 21+ analytics tests with comprehensive fixtures
- Added model, sensor definition, hourly helper, and edge case tests
- Test conftest with HA module mocking for standalone test execution
- Added `pyproject.toml` with pytest, ruff, and mypy configuration

### Cleanup
- Deleted deprecated `home_assistant_example/` prototype
- Deleted diverged standalone `ovo_australia_client.py`
- Deleted legacy `test_integration.py`
- Deleted contradicting `requirements.txt`
- Moved documentation to `docs/guides/` and `docs/dashboards/`
- Moved install scripts to `scripts/`
- Added `CLAUDE.md` project guide

---

## [3.0.0] - 2026-01-21

### 🚀 Intelligent Auto-Configuration Release

This is a **major release** that fundamentally changes how the integration is configured. Setup is now **fully automatic** - just enter your credentials and everything else is detected from OVO's API.

### Added

- **Automatic Plan Detection** - Integration now fetches your energy plan directly from OVO's GraphQL API
- **Auto-Detected Rates** - All energy rates (peak, shoulder, off-peak, EV, feed-in tariff) are automatically extracted from your OVO account
- **Plan Information Sensor** - New diagnostic sensor displays your current plan name, rates, NMI, and agreement details
- **Intelligent Plan Mapping** - Automatically identifies your plan type (The EV Plan, The Free 3 Plan, The Basic Plan, The One Plan)
- **Rate Conversion** - Automatic conversion from cents/kWh (API format) to $/kWh (display format)

### Changed

- **Simplified Setup Flow** - Reduced from 3+ steps to just 2 steps (email + password only)
- **Config Flow Optimization** - Reuse authenticated client to prevent double authentication during setup
- **Better User Experience** - No more guessing your plan type or manually entering rates

### Removed

- **Manual Plan Selection Step** - No longer needed thanks to automatic detection
- **Manual Rate Entry** - Rates are now fetched from OVO API instead of user input

### Technical

- Added `GetProductAgreements` GraphQL query to const.py
- Implemented `get_product_agreements()` method in api.py
- Added `_detect_plan_from_api()` method to config_flow.py
- Enhanced `OVOEnergyAUPlanSensor` to display real-time plan information from API
- Updated strings.json and translations/en.json to reflect v3.0.0 features
- Updated README.md with v3.0.0 features and HACS auto-install button

### Breaking Changes

⚠️ **Important for existing users:**

- If you're upgrading from v2.x, you may need to reconfigure the integration
- Plan type and rates will be automatically detected on next setup
- Your existing sensors will continue to work, but you'll get more accurate pricing
- Manual rate customization is still available via integration options (Configure button)

---

## [2.4.0] - 2026-01-20

### Major Analytics Release

### Added

- ✨ **10 comprehensive energy analytics features**
- 📊 **32 new sensors** for advanced insights
- 🧠 Peak usage time block identification (4-hour windows)
- 📈 Week-over-week comparison tracking with % changes
- 📅 Weekday vs weekend analysis
- ⏰ Time-of-use cost breakdown (Peak/Shoulder/Off-Peak)
- ☀️ Solar self-sufficiency score (0-100%)
- 🏆 High usage day rankings (top 5 consumption days)
- 🗺️ Hourly heatmap data for visual dashboards
- 💰 Cost per kWh tracking (overall, grid, solar)
- 🔮 Monthly cost projection and budget forecasting
- 💸 Return-to-grid value analysis and solar ROI tracking
- 🎨 10 new device categories for better organization
- 📋 Comprehensive sensor attributes for dashboard customization

### Technical

- **Total Sensors:** 80+ (48 existing + 32 new analytics sensors)
- Enhanced sensor.py with advanced analytics calculations
- Improved data coordinator with rolling window calculations
- Added detailed sensor attributes for ApexCharts and custom cards

---

## [2.3.0] - 2026-01-20

### Sensor Organization Release

### Added

- 🎯 Device categories for logical sensor grouping
- 📁 8 main device groups (Yesterday, This Month, This Year, Hourly Data, Last Week, Last Month, Month to Date, 3 Day Snapshot)
- 🎨 Cleaner sensor names following Home Assistant best practices
- ✨ Better Home Assistant UI organization and navigation

### Changed

- Reorganized all sensors into logical device categories
- Improved sensor naming conventions for consistency
- Enhanced device info for better entity management

---

## [2.2.0] - 2026-01-20

### Historical Period Sensors Release

### Added

- 📅 **Last 7 Days sensors** (4 total: solar consumption, solar charge, grid consumption, grid charge)
- 📆 **Last Month sensors** (4 total: complete previous month data)
- 📊 **Month to Date sensors** (4 total: current calendar month progress)
- 🗓️ **Dynamic 3-day sensors** with actual day names and dates
  - 12 sensors total (4 per day)
  - Automatically updates day labels (e.g., "Monday 20 Jan")
  - Shows solar consumption, solar charge, grid consumption, grid charge
- ✨ Automatic date formatting and labeling

### Technical

- Added historical period calculations to coordinator
- Implemented dynamic date-based sensor naming
- Enhanced data processing for rolling windows

---

## [2.1.0] - 2026-01-20

### Monthly Breakdown Release

### Added

- 📊 Monthly charge graphs with daily breakdown
- 📈 Daily statistics (average, max, daily totals)
- 🎨 Dashboard examples with ApexCharts configuration
- 📋 Complete daily breakdown in sensor attributes

### Changed

- Enhanced monthly sensors with detailed attributes
- Improved data structure for better dashboard integration
- Added ApexCharts examples to README

---

## [2.0.0] - 2026-01-20

### Config Flow & Auto-Refresh Release

This was the first major release introducing the Home Assistant UI configuration flow.

### Added

- ✅ **Home Assistant UI configuration flow** - No more YAML editing
- 🔄 **Automatic token refresh** - OAuth 2.0 with automatic re-authentication
- 🎯 **OAuth 2.0 authentication** - Secure Auth0 integration
- ✨ **No YAML configuration needed** - Everything done through UI
- 🔐 **Secure token storage** - Encrypted credential storage in Home Assistant

### Removed

- ❌ Removed YAML configuration requirement
- ❌ Removed manual token management

### Technical

- Implemented ConfigFlow and OptionsFlow handlers
- Added OAuth 2.0 authentication with Auth0
- Implemented automatic token refresh mechanism
- Added DataUpdateCoordinator for efficient API polling
- Enhanced error handling and logging

---

## [1.x] - 2025-2026

### Initial Development

- Basic sensor implementation
- YAML-based configuration
- Manual token management
- Core energy tracking features
- GraphQL API integration
- Daily, monthly, and yearly sensors

---

## Future Plans

- [ ] Support for multiple tariff structures
- [ ] Enhanced solar export analytics
- [ ] Integration with Home Assistant Energy dashboard
- [ ] Custom dashboard templates
- [ ] Advanced cost optimization recommendations
- [ ] Battery storage support (if/when OVO adds it)

---

## Support

- **Issues:** https://github.com/HallyAus/OVO_Aus_api/issues
- **Discussions:** https://github.com/HallyAus/OVO_Aus_api/discussions
- **Support Development:** https://buymeacoffee.com/printforge
