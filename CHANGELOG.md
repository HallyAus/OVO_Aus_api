# Changelog

All notable changes to the OVO Energy Australia Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
