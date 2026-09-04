# Changelog

All notable changes to the OVO Energy Australia Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [4.9.2] - 2026-09-05

> - **OVO referral code:** `daniel16485`
> - **Direct OVO signup:** [https://www.ovoenergy.com.au/refer/daniel16485](https://www.ovoenergy.com.au/refer/daniel16485)
> - **Friendly link:** [https://ovoreferralcode.com/](https://ovoreferralcode.com/)

### Changed
- Declared Australia in `hacs.json` so the integration can be submitted to the default HACS catalogue with the correct country filter.
- Changed the repository license from CC0-1.0 to the OSI-approved MIT license so current HACS validation accepts the project.
- CI now installs the project with its development dependencies before running tests and uses the current Node.js 24-based checkout/setup actions.
- The README now shows release-download information, clearer support links, and a friendly invitation for OVO to discuss an official supported API pathway.

## [4.9.1] - 2026-09-04

> - **OVO referral code:** `daniel16485`
> - **Direct OVO signup:** [https://www.ovoenergy.com.au/refer/daniel16485](https://www.ovoenergy.com.au/refer/daniel16485)
> - **Friendly link:** [https://ovoreferralcode.com/](https://ovoreferralcode.com/)

### Added
- Added The Free 4 Plan and Basic Free 4 recognition, including the complete 11am-3pm free window and support for `FREE_4` usage buckets without creating more entities (#78).
- Plan Information and Current Tariff Period now expose the applicable free, EV, super-off-peak, and configured peak windows as attributes.

### Fixed
- Transient hourly API failures and structurally empty responses now retain the last good hourly payload instead of publishing a synthetic set of zero totals.
- A cold start without usable hourly entries keeps hourly-only entities unavailable until real data arrives.
- Integration Health and privacy-safe diagnostics now distinguish fresh, stale-cached, and unavailable hourly data and report the last successful hourly update.
- Existing entries now detect a recognised OVO plan change on refresh unless the user has deliberately selected a plan in integration options (#78).
- Plan changes now select the latest active agreement rather than assuming OVO returns it first, and automatic entries refresh their fallback rates from that agreement.
- Free 3/Free 4 always report the contractual $0 rate in the free window even if OVO returns an unrelated non-zero super-off-peak placeholder.
- The Free 3 tariff indicator now uses the configured peak window and reports Peak/Off-Peak with the matching live or configured rates instead of labelling every paid period Standard (#82).
- A non-zero One Plan or EV super-off-peak rate is now reported as Super Off-Peak rather than FREE; the reported United Energy One Plan 11am-4pm period uses its actual API price, follows a configured afternoon peak boundary, and never exposes an EV period (#79).
- The account device is explicitly registered before category or vehicle entities reference it, and child devices use Home Assistant's current `via_device_id` API (#77).
- Multi-account contact lookup no longer falls back to a different active account when the configured account is absent.
- The v4.9 registry migration removes the 161 retired rotating entities that produced v4.8.2's state-class repairs; upgrade guidance now explains how to discard any orphaned statistics that Home Assistant still offers to delete (#80).
- HACS and the README now declare Home Assistant 2026.8.3 as the minimum after older Container installations failed to resolve the required PyJWT version (#81).

### Validation
- Added consecutive-refresh regressions for exception, empty-response, cold-start, and recovery paths.
- Added a contract test that the nine rolling week/hour replacement entities remain without a long-term-statistics state class.
- Added plan-detection, active-agreement, live-rate refresh, contractual-free-rate, Free 4, Free 3 TOU, paid super-off-peak, Free 4 bucket compatibility, multi-account isolation, and parent-device registration regressions.

## [4.9.0] - 2026-08-27

> - **OVO referral code:** `daniel16485`
> - **Direct OVO signup:** [https://www.ovoenergy.com.au/refer/daniel16485](https://www.ovoenergy.com.au/refer/daniel16485)
> - **Friendly link:** [https://ovoreferralcode.com/](https://ovoreferralcode.com/)

### Fixed
- High Usage Days now ranks actual household use (grid import plus self-consumed solar) instead of treating exported solar as consumption.
- Week comparison, weekday/weekend, high-usage, and effective-cost analytics now use grid charges less export credits. Their names and attributes explicitly say the figures exclude supply charges.
- Integration Health now identifies OVO usage as next-day, non-real-time data and reports the newest usage date, delay in days, and stale status.

### Changed
- Removed 140 rotating Day 1-7 entities and 21 rotating hourly-day entities. Stable period summaries, Yesterday Hourly attributes, totals, and heatmap data remain available. The account surface falls from 281 to 105 entities; one vehicle adds 19 on its own linked device.
- Consolidated six tariff-rate entities into Plan Information attributes, keeping Current Tariff Period as the normal tariff entity.
- Consolidated daily/monthly/yearly OVO savings into the single Plan Savings entity and the three latest-bill values into Latest Bill.
- Removed the incomplete Monthly Forecast and retained Bill Estimate as the only forecast because it includes standing charges and export credits.
- Updated bundled dashboards and documentation for the smaller, corrected entity surface.
- Updated the Daily Savings Report blueprint to read daily/monthly values from Plan Savings attributes; existing blueprint automations should be reconfigured to select that entity.

### Validation
- Added regression coverage for solar export-heavy days, net-cost comparisons, consolidated entities, removed rotating entities, and delayed/stale usage reporting.

## [4.8.2] - 2026-08-20

> - **OVO referral code:** `daniel16485`
> - **Direct OVO signup:** [https://www.ovoenergy.com.au/refer/daniel16485](https://www.ovoenergy.com.au/refer/daniel16485)
> - **Friendly link:** [https://ovoreferralcode.com/](https://ovoreferralcode.com/)

### Fixed
- Connected vehicles now use the portal's separate, account-scoped Kaluza OAuth sign-in before requesting the Firebase account token. The previous implementation incorrectly sent the normal MyOVO access token to that endpoint, so valid vehicles were silently absent from Home Assistant.
- Kaluza access tokens are cached and their refresh tokens are preferred. The MyOVO password/SSO path is used only when no usable Kaluza refresh token remains.
- MyOVO sign-in now tolerates OVO's intermittent omission of the ID-token nonce after OAuth state and PKCE validation. A returned nonce is still compared in constant time and any mismatch is rejected.
- Vehicle authentication failures now emit one clear warning, report `vehicle_status` in privacy-safe diagnostics, and log subsequent repeated failures at debug level instead of silently returning an unexplained empty set.

### Validation
- Reproduced the current two-stage MyOVO/Kaluza PKCE flow against the live platform and verified one connected vehicle through the released integration client path, including telemetry, charge plan, charging settings, and monthly EV energy.
- Added regressions for Kaluza SSO parameters, refresh-first token reuse, missing/mismatched nonce handling, account-to-customer matching, and vehicle status reporting.

## [4.8.1] - 2026-08-19

> - **OVO referral code:** `daniel16485`
> - **Direct OVO signup:** [https://www.ovoenergy.com.au/refer/daniel16485](https://www.ovoenergy.com.au/refer/daniel16485)
> - **Friendly link:** [https://ovoreferralcode.com/](https://ovoreferralcode.com/)

### Fixed
- Restored category-specific Home Assistant devices after 4.8.0 incorrectly merged approximately 281 entities onto the single account device. Entities are grouped by their existing categories again, with the account device retained as their parent.
- Connected-vehicle discovery no longer depends on `flex.hasOnboarded`. That GraphQL flag describes a separate MyOVO Flex state and can be false for an account that has a valid EV Control vehicle, which caused all 19 vehicle entities to be skipped in 4.8.0.
- Added regressions covering category device identifiers and vehicle discovery when the unrelated Flex flag is false.

## [4.8.0] - 2026-08-19

> - **OVO referral code:** `daniel16485`
> - **Direct OVO signup:** [https://www.ovoenergy.com.au/refer/daniel16485](https://www.ovoenergy.com.au/refer/daniel16485)
> - **Friendly link:** [https://ovoreferralcode.com/](https://ovoreferralcode.com/)

### Added
- **Complete connected-vehicle support** - Accounts enrolled in OVO EV Control now get a separate vehicle device with 19 entities covering battery state of charge, estimated range, cable state, charging mode, boost state, charge limit, charge/telemetry timestamps, battery capacity, min/max charging power and SOC, monthly vehicle energy/cost, registration/readiness, credential and vendor health, charging preferences, weekly/tariff schedules, demand-period configuration, and every returned charge-plan interval. Multiple vehicles and vehicles discovered after setup are supported.
- **Privacy-filtered Kaluza/Firebase client** - Implements the portal's short-lived account-token chain and verified GET endpoints for registration, vehicles, current-month device energy, charge plans, and charging times. Tokens are cached within their lifetime and refreshed once after rejection.
- **Live billing summary** - New sensors for next/minimum direct debit, unbilled electricity, unbilled solar credit, and current bill progress.
- **Privacy-safe diagnostics and documented refresh action** - Diagnostics report availability/counts without bills, addresses, meter/device/account IDs, VIN, location, or tokens. `ovo_energy_au.refresh_data` is now documented under Developer Tools → Actions.

### Fixed
- OAuth callback `state` and ID-token `nonce` are now validated before tokens are accepted.
- Refresh tokens are preferred over repeated password submission; rate limiting now uses a monotonic clock.
- Bill estimates subtract the actual return-to-grid credit instead of solar-generation charges.
- Last-seven-day hourly analytics use an exact Sydney-time window.
- Tariff-period status is plan-aware and uses detected live rates rather than claiming EV/free periods for every plan.
- Moving day/history entities no longer publish misleading long-term statistic state classes.
- Multi-account balance matching, per-kWh four-decimal precision, and invalid-auth mapping from the 4.7.1 source baseline are included in this published release.

### Changed
- Runtime state uses `ConfigEntry.runtime_data`; integration-level actions are registered once; options save with automatic entry reload.
- The declared minimum Home Assistant version is now the accurate **2024.6**, when `ConfigEntry.runtime_data` became available; options reload without requiring the newer 2025.8 helper.
- Detailed daily/hourly history entities start disabled to reduce Recorder and registry load.
- Account energy entities share one account device; connected vehicles use linked physical devices with opaque hashed identifiers.
- HACS and Home Assistant now receive transparent local brand assets using the current OVO mark and a proper horizontal wordmark; the opaque white-square/lightning artwork was removed.
- The sign-in page and release-note generator put referral code `daniel16485`, the complete direct OVO URL, and the friendly URL first.
- Installers, HACS/setup guides, translations, blueprint syntax, and historical API documentation were corrected and hardened against token/account-data disclosure.
- PyJWT is constrained to `>=2.13,<3`.

### Security
- VIN, coordinates, home-presence flags, raw account/user/device/optimisation/tariff IDs, tokens, and vendor certificate URLs are discarded before vehicle data reaches Home Assistant.
- Signed statement URLs, NMIs, and account IDs were removed from Recorder-visible entity attributes.
- The vehicle implementation is intentionally read-only. Boost, schedule/limit mutation, unlink/remove, and other control actions are not invoked or exposed.

## [4.7.1] - 2026-07-17

### Bug Fixes
- **Per-kWh rate sensors no longer truncated to 2 decimals** - The **Peak Rate**, **Shoulder Rate**, **Off-Peak Rate**, **EV Off-Peak Rate**, **Feed-in Tariff**, **Cost per kWh** (overall/grid/solar) and **Export Rate per kWh** sensors were rounded to 2 decimal places in Home Assistant, so a $0.3718/kWh peak rate showed as $0.37 and a 3.3c feed-in tariff as $0.03 (a 9% error). AUD/kWh sensors now keep 4 decimals; all other sensors are unchanged
- **Multi-account: Account Balance now comes from the right account** - The balance and solar flag were read from the first active account returned by the API instead of the account this integration is configured for. Customers with more than one active OVO account could see another account's balance
- **Config flow shows the right error** - A missing account ID after a successful login was reported as "cannot connect" instead of an authentication problem

## [4.7.0] - 2026-07-05

### New Features
- **Configurable billing cycle start day (#75)** - New **Billing Cycle Start Day (1-31)** option in the integration's Configure dialog. If your OVO bill doesn't start on the 1st (e.g. a 24th–23rd cycle), set it to the day your cycle begins and the **Month to Date**, **Last Month**, **Bill Estimate**, and **Monthly Forecast** sensors follow your real billing period instead of the calendar month. Defaults to 1 (calendar month), so existing installs are unchanged. Per-month clamping handles short months and the value survives year boundaries.

### Notes
- The **This Month** / **This Year** / **OVO Savings (This Month)** / **EV Charging This Month** sensors are sourced directly from OVO's own monthly/yearly API aggregation (what the OVO app shows) and continue to use OVO's periods. Billing-cycle awareness applies to the figures the integration derives from daily data.

## [4.6.0] - 2026-06-14

### New Features
- **OVO Flex onboarding status** - New diagnostic sensor `flex_onboarded` ("Onboarded"/"Not Onboarded"). The field name (`flex { hasOnboarded }`) was recovered by scanning the OVO web app's bundled GraphQL operations; `hasOnboarded` is the only field the API exposes under `flex` (no balance/VPP data exists). Folded into the existing account-extras query (no extra request)

### Notes
- `GetNotificationInfo` is intentionally **not** exposed: its input requires an `fcmToken` (a mobile push-notification token) that a Home Assistant integration cannot provide. This was confirmed against the live API. The OVO GraphQL surface is now fully mapped and everything usable from a server-side integration is exposed

## [4.5.0] - 2026-06-14

### New Features
- **Payment history** - New `GetAccountExtras` query exposes your payments (verified live). A `Latest Payment` sensor shows the most recent amount, with date, type (DIRECT_DEBIT / TOP_UP), payment count, and a `recent_payments` history list in its attributes
- **Refer-a-friend earnings** - A `Referral Earnings` sensor shows your total OVO referral credit earned, with your referral code and referral count in attributes (the raf API sub-fields take a per-field `input` arg, handled in the query)

### Maintenance
- `tests/` now passes `ruff check` cleanly (removed unused imports, sorted imports, moved conftest's datetime import out of the post-mock block). No behaviour change

## [4.4.0] - 2026-06-14

### New Features
- **Home Assistant Energy Dashboard support (#73)** - Three purpose-built sensors feed HA's built-in Energy Dashboard: `energy_grid_import`, `energy_grid_export`, `energy_solar_production`. They expose cumulative month-to-date totals with `state_class=total` and a monthly `last_reset` — the form the Energy Dashboard expects — so the existing point-in-time "Yesterday" sensors no longer need to be (incorrectly) used there. Add them under Settings → Energy. (OVO publishes usage ~1 day delayed, so the dashboard fills in a day behind.)

## [4.3.0] - 2026-06-14

### New Features
- **Real bills (statements)** - New `GetStatements` query exposes your actual issued bills (verified against the live API). New sensors: `latest_bill_amount`, `latest_bill_closing_balance`, `latest_bill_opening_balance`, plus a `Latest Bill` sensor whose attributes include the billing period, issue date, balances, a PDF `download_url`, and a `recent_bills` list. This is real billed data, complementing the existing `bill_estimate_*` projections
- **Real plan rates as sensors (#63)** - New `Tariff Rates` sensors surface your actual plan rates from the API (`tariff_peak_rate`, `tariff_shoulder_rate`, `tariff_off_peak_rate`, `tariff_ev_off_peak_rate`, `tariff_feed_in_rate`, `tariff_standing_charge`). The manual rate config is already auto-populated from the API at setup; these expose the live values too
- **`Grid Consumption (Last 3 Days)` sensor** - Surfaces the previously-computed-but-unexposed `last_3_days` aggregation (orphan-namespace gap), with per-day detail in attributes

### Notes
- The hourly free/EV usage trackers (`hourly.free_usage`, `hourly.ev_usage`, `hourly.ev_usage_weekly`) are intentionally **not** exposed: the hourly API returns no rate labels, so they always compute 0 (verified). The real free/EV figures are exposed via the interval `rate_breakdown` sensors (`{period}_free_3_*`, `{period}_ev_offpeak_*`, EV charging sensors)

## [4.2.2] - 2026-06-14

### Bug Fixes
- **Peak/Off-Peak TOU split now actually works on real data (#74)** - The v4.2.1 sensors read 0 in production. Verified against the live API: `GetHourlyData` returns `rates: null` and `charge: null` for every hour, so rate-less grid usage was defaulting to the `shoulder` bucket and `_split_other_by_window` (which only re-buckets `OTHER`) never matched. Rate-less hourly grid usage is now labelled `OTHER`, so the configured Free 3 peak window correctly splits it into peak/off-peak by hour. The unit tests now use realistic rate-less fixtures (matching the actual API) so this can't regress
- **Time-of-use no longer counts solar generation** - `_compute_tou_breakdown` now only sums grid entries; solar entries were inflating the breakdown

### Changed
- **Removed `tou_peak_cost` / `tou_off_peak_cost` sensors** - The hourly API provides no per-hour cost, so these could only ever read 0. The `tou_peak_consumption` / `tou_off_peak_consumption` (kWh) sensors remain and now populate correctly for Free 3 plans with a configured peak window

## [4.2.1] - 2026-06-14

### Bug Fixes
- **Peak/Off-Peak TOU sensors now exposed (#74)** - v4.2.0 computed the time-of-use peak/off-peak split (and re-bucketed `OTHER` usage into peak/off-peak for Free 3 plans) but never surfaced it as entities, so the calculated values were unreachable in Home Assistant. Four new sensors expose it: `tou_peak_consumption`, `tou_peak_cost`, `tou_off_peak_consumption`, `tou_off_peak_cost` (grouped under a "Time of Use" device, last-7-days window). They populate for Free 3 plans once the peak window is configured, and for any plan with native PEAK/OFF_PEAK rate types

### Tests
- New real-data regression tests assert the TOU value functions read the correct `hourly.time_of_use` path (75 tests total)

---

## [4.2.0] - 2026-06-11

### New Features
- **Free 3 Peak/Off-Peak Split (#63)** - New `peak_start_hour`/`peak_end_hour` options (shown for the Free 3 plan) re-bucket `OTHER` usage into peak/off-peak in the time-of-use breakdown. Supports overnight windows (e.g., 21 → 7); set both to the same value to disable

### Bug Fixes
- **CRITICAL: Fixed off-peak per-day rate sensors always reporting 0** - Sensors looked up `OFFPEAK` but the API charge type is `OFF_PEAK`; entity IDs are unchanged
- **Fixed daily date bucketing using UTC dates** - Interval entries are now converted to `Australia/Sydney` before extracting the date, matching the hourly pipeline (entries near midnight no longer land on the wrong day)
- **Fixed hourly query window using HA-local time** - The 8-day hourly fetch window now uses Sydney time, so HA instances configured in other timezones request the correct dates
- **Fixed token-refresh loop with short-lived tokens** - The refresh buffer is now capped at half the token lifetime, preventing full re-authentication on every request
- **Fixed reauth allowing a different OVO account** - Re-authenticating with credentials for another account now aborts with a clear error instead of silently repointing the entry
- **Fixed rate-breakdown percentages exceeding 100%** - Percentages are recomputed after merging entries instead of being summed
- **Fixed peak 4-hour window spanning data gaps** - Windows are now required to be 4 contiguous hours
- **Fixed auth errors being swallowed by secondary fetches** - Authentication failures from product agreements/contact info/usage info now correctly trigger reauth
- **Removed response body from login error messages** - Prevents any possibility of credential material reaching logs
- **Day-rate sensors now report unavailable (not 0) when history is missing**
- **EV charging monthly/yearly kWh sensors now use TOTAL_INCREASING** - Correct statistics at month/year rollover
- **Annual savings projection skips the first 2 days of a month** - Avoids wildly unstable extrapolations

### Improvements
- README/info.md now warn against selecting HA's built-in **OVO Energy** (UK) integration (#72) and the quick-example entity IDs were corrected
- Multi-account holders get a logged warning that the first account is used
- Analytics now use a single mockable clock source (`dt_util.now(AU_TIMEZONE)`), making the test suite deterministic year-round
- `tzdata` added to dev dependencies so tests run on Windows/slim containers
- New tests: peak window splitting, PlanConfig window round-trip (72 tests total)

---

## [4.1.1] - 2026-04-22

### Bug Fixes
- **#66 / #65** - Fixed `AttributeError: 'OVOEnergyAUDataUpdateCoordinator' object has no attribute 'last_update_success_time'` spamming logs every coordinator refresh. Coordinator now inherits from `TimestampDataUpdateCoordinator`, which provides `last_update_success_time` as a proper datetime. Integration Health sensor now populates correctly.
- **#64** - Fixed duplicate per-day sensors with `_2`, `_3`, `_4` suffixes. Dynamic day sensors (`OVODaySensor`, `OVODayRateSensor`) now include the day number in their display name so Home Assistant's entity-id slugification produces unique IDs. Affected sensors: `day_N_solar_consumption`, `day_N_grid_rate_*_consumption`, `day_N_grid_rate_*_charge`, etc.
- **#54** - Fixed `DASHBOARD_GUIDE.md` sensor references missing the `ovo_energy_au_` entity prefix (e.g., `sensor.daily_solar_consumption` → `sensor.ovo_energy_au_daily_solar_consumption`). All daily/monthly/yearly/hourly references corrected.
- **#58** - Bumped manifest version to 4.1.1 so HACS displays the semantic version. Note: a matching `v4.1.1` GitHub release/tag must be created for HACS to resolve the version correctly.

---

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
