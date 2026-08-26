# OVO Energy Australia (HA integration) — agent brief

Home Assistant custom integration that pulls OVO Energy Australia usage/billing/EV data via
OVO's GraphQL API and exposes it as sensors. Installed by real strangers through HACS.
Status: **live** — public repo `HallyAus/OVO_Aus_api`, latest release **v4.9.0** (2026-08-27) · verified 2026-08-27

## What a mistake costs
Every release lands in strangers' Home Assistant installs. A bad one breaks their dashboards,
their Energy Dashboard history, or their login — and they cannot roll back easily.
The integration handles a **cleartext MyOVO password** and account PII (NMI, address, account ID,
VIN, GPS). Leaking any of it into logs, entity attributes, or diagnostics is the worst outcome here;
Recorder persists attributes to disk forever. Renaming or deleting an entity silently breaks
user dashboards and long-term statistics. Referral income is the only funding, so repo reputation matters.

## Stack
- Python 3.11+, `aiohttp` + `PyJWT` only. `PyJWT>=2.13,<3` is pinned — 3.x breaks the API surface.
- Home Assistant **2024.6** minimum, chosen because that is when `ConfigEntry.runtime_data` landed. Do not raise it casually.
- Auth is **Auth0 OAuth2 + PKCE scraping the HTML login form**, not a public API. See archived notes for the 6-step flow.
- EV data comes from a **separate Kaluza/Firebase token chain**, account-scoped — NOT the MyOVO access token.
- Tests mock the entire `homeassistant` package in `tests/conftest.py`. HA is **not** installed; `pip install homeassistant` is unnecessary.
- `ruff` (line-length 120, E501 ignored) + `mypy` + `pre-commit` with `detect-secrets`.
- Distribution is **HACS**, which installs from the latest **GitHub release tag** — never from `main`.

## Run it
```bash
python -m pytest tests/ -q                      # 141 tests, ~0.4s, no HA needed
python -m pytest tests/test_analytics.py -v -k name
ruff check custom_components/ovo_energy_au/
mypy custom_components/ovo_energy_au/
pre-commit run --all-files
```

## Where things live
| To change | Edit |
|---|---|
| A sensor (add/remove/rename/unit) | `custom_components/ovo_energy_au/sensors/definitions.py` — data tuples, not constructors |
| Vehicle sensors | `custom_components/ovo_energy_au/sensors/vehicle.py` |
| A GraphQL query | `custom_components/ovo_energy_au/graphql/queries.py` |
| Auth, token refresh, rate limiting | `custom_components/ovo_energy_au/api.py` |
| Kaluza/EV client + privacy filter | `custom_components/ovo_energy_au/vehicle.py` |
| Plan names, default rates, endpoints, intervals | `custom_components/ovo_energy_au/const.py` |
| What is fetched each poll (5 min) | `custom_components/ovo_energy_au/coordinator.py` |
| Setup/options/reauth UI + its text | `config_flow.py` + `strings.json` + `translations/en.json` |
| What diagnostics may expose | `custom_components/ovo_energy_au/diagnostics.py` |
| Cost/savings/comparison maths | `analytics/interval.py`, `analytics/hourly.py`, `analytics/insights.py`, `analytics/billing.py` |
| Version (must match in all four) | `manifest.json`, `pyproject.toml`, `README.md` badge, `info.md` badge |

## Rules that bite
1. **A version bump without a GitHub release ships nothing.** HACS resolves from the latest release
   tag. Bump the four files, add a `CHANGELOG.md` entry, commit, push, then
   `gh release create vX.Y.Z --target main`. Verify `gh release list` shows it as **Latest**.
   This has already been missed once — v4.7.1 has no tag and never reached users. See LEARNINGS.md.
2. **Never build the release zip with PowerShell `Compress-Archive`.** On Windows PowerShell 5.1 it
   writes backslash entry paths that extract as one mangled file on Linux/macOS, where most HA users
   are. Use the Python `zipfile` one-liner in the archived notes, or let `release.yml` do it.
3. **Never interpolate exception text into auth logs.** The login payload carries the cleartext
   password. `api.py` uses static messages plus `type(err).__name__` — keep it that way.
4. **VIN, coordinates, home-presence, raw account/user/device/optimisation IDs, tokens and vendor
   certificate URLs must never reach Home Assistant.** They are dropped in `vehicle.py` before the
   data is returned. Entity attributes go into Recorder permanently.
5. **The vehicle integration is deliberately read-only.** Boost, schedule/limit mutation, unlink and
   other control actions are not invoked and not exposed. Do not add them without an explicit decision.
6. **Money is AUD dollars everywhere; the API returns cents — divide by 100.** Per-kWh sensors keep
   **4 decimals** (2 turned a 3.3c feed-in tariff into $0.03, a 9% error).
7. **All date maths uses `AU_TIMEZONE` (`Australia/Sydney`)**, never naive local time — AEST/AEDT
   transitions silently shift daily totals otherwise.
8. **`CREDIT` = solar export to grid; every other charge type is grid consumption.** Getting this
   backwards makes exported solar look like household usage.
9. **`git fetch origin` and rebase before committing.** Remote `main` moves via cloud-agent PRs between local sessions.

## Danger zone
- 2026-08-27: v4.9.0 deliberately removes 140 rotating Day 1-7 plus 21 rotating hourly-day entities and
  consolidates tariff/savings/latest-bill entities. Existing dashboards and automations must move to the
  stable summary entities and attributes documented in the 4.9.0 upgrade notes.
- 2026-08-27 (verified): **pushing a `v*` tag is the ship button.** `.github/workflows/release.yml` fires on
  `push: tags: v*` (and on `workflow_dispatch` with a tag input, which creates the tag itself) with
  `contents: write`, and HACS serves the newest release to every installed user. There is no undo — users
  who have already upgraded stay upgraded.
- Live users receive v4.9.0 through HACS. Entity `unique_id` is
  `f"{coordinator.account_id}_{sensor_key}"` (`sensors/base.py:44`) — changing a key orphans the entity and
  loses its long-term statistics history.
- No staging environment. Verification against the real OVO platform means logging into a real
  account; probes must be read-only and leave no credentials behind.

## State of play — 2026-08-27
**Done and live:** v4.9.0 on HACS — 105 account entities, HA Energy Dashboard sensors, real bills,
live tariff rates, payment history, referral earnings, configurable billing-cycle day, connected-vehicle
(EV Control) support with privacy filtering, privacy-safe diagnostics, `ovo_energy_au.refresh_data` action.
Entity-surface reduction, corrected net-cost/household-use analytics, delayed-data health reporting,
connected vehicles, updated dashboards, and the consolidated Daily Savings blueprint are included.
Local tests: 141 passed; CI is configured for ruff + pytest + hassfest + HACS validation.
**Deliberately not done:** `GetNotificationInfo` (needs an `fcmToken` a server-side integration cannot
supply); EV write/control actions; home-assistant/brands submission (custom integrations are no longer
accepted — branding lives in `custom_components/ovo_energy_au/brand/`).
**Next:** monitor upgrade feedback, especially stale dashboard references to retired entities.

## Traps
- OVO publishes usage with **about a day's delay**. "Missing today's data" is normal, not a bug.
- The hourly API returns `rates: null` **and** `charge: null` on some accounts; entry-level
  `charge.type` is only a DEBIT/CREDIT direction, never a TOU rate. Unclassified hours must be labelled
  `OTHER` so the Free-3 window split can re-bucket them — defaulting to `shoulder` silently broke it.
- `flex.hasOnboarded` describes MyOVO Flex, **not** EV Control. Gating vehicle discovery on it hid all
  19 vehicle entities in v4.8.0.
- `const.py` calls `ZoneInfo("Australia/Sydney")` at import time; Windows and slim containers have no
  system tzdata, so `tzdata` is a required dev dependency or every test fails at collection.
- CI can be blocked by GitHub Actions billing locks (`gh run view` reports it). Do releases manually then.

## Deeper context (load only when needed)
- `LEARNINGS.md` — incidents that cost real time; read before touching releases, vehicles or hourly analytics.
- `docs/legacy-agent-notes-2026-08-26.md` — full module map, the 6-step Auth0 flow, the exact release-zip command.
- `docs/guides/AUDIT_REPORT.md` — 2026-08 full repository/platform audit.
- `docs/guides/OVO_AU_API_DOCUMENTATION.md` — mapped GraphQL surface. `docs/actions.md` — the service.
