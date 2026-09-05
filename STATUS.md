# Current status — OVO Energy Australia

Volatile project state for coding agents and maintainers. Update this file when release/runtime/CI truth changes. Do not put permanent engineering rules here; those belong in `AGENTS.md`. Historical incidents belong in `LEARNINGS.md`.

Verified: 2026-09-05.

## Production / release

- Latest stable GitHub/HACS release: **v4.9.3**.
- Latest stable release target: `b7191988d4c7faf28b5697cdad6f8b6a1c4cbdfc`.
- Current `main` source version: **4.10.0** (release preparation committed, not yet the latest published release at the time of this verification).
- Current `main` head at verification: `2a849bf007fa3f04c48cd385bc3a191a56f284e7` (`chore(release): prepare v4.10.0`).
- Distribution: HACS resolves from the latest GitHub release; a version present only on `main` has not shipped to users.

## Supported runtime

- Home Assistant minimum advertised/enforced by HACS: **2026.8.3**.
- Python support: 3.11+; CI unit checks currently run on Python 3.12.
- Home Assistant runtime regressions currently run on Python 3.14 using `requirements-test-ha.txt`.
- Runtime dependency: `PyJWT>=2.13.0,<3.0.0`.
- Timezone authority: `Australia/Sydney`.

## CI gates

`.github/workflows/ci.yml` currently runs on pushes/PRs to `main` and contains five gates:

1. Ruff lint (`custom_components/ovo_energy_au/`).
2. Unit/packaging tests (`pytest tests/ -v`).
3. Home Assistant hassfest.
4. HACS integration validation.
5. Actual Home Assistant runtime regressions (`pytest tests_ha/ -q --asyncio-mode=auto`).

Treat exact test counts as volatile; inspect the current run rather than copying old counts from README/docs.

## Current product state

- Cloud-polling Home Assistant integration for OVO Energy Australia.
- Auth: Auth0 OAuth2 + PKCE against the MyOVO web flow; there is no supported public OVO developer API contract for this integration.
- EV data: optional read-only OVO EV Control/Kaluza integration using a separate token chain.
- Energy Dashboard totals use source-period-aware reset dates so delayed OVO data is not re-anchored to the wrong month.
- Missing hourly data is represented as unknown rather than zero.
- Active tariff/product selection excludes future/expired agreements and separates solar export credits from grid-import tariff buckets.
- Vehicle commands/mutations remain deliberately unsupported.

## Current operational constraints

- OVO normally publishes usage about a day late. Do not treat absence of today's readings as an outage by itself.
- Live platform verification requires a real OVO account. Any such probe must be read-only and credentials must not be persisted to source, logs, CI, issues or artifacts.
- Auth and API behaviour can change upstream without notice because the integration follows OVO's web/API behaviour rather than a stable public developer contract.

## Before starting substantial work

1. Confirm remote `main` still points to the expected current commit.
2. Read `AGENTS.md`.
3. Read relevant entries in `LEARNINGS.md` for auth, vehicles, analytics, entity identity or releases.
4. Inspect current open issues and recent CI if the task concerns a reported regression.
5. Update this file if the work changes any volatile truth above.
