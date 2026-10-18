# Current status — OVO Energy Australia

Volatile project state for coding agents and maintainers. Update this file when release/runtime/CI truth changes. Do not put permanent engineering rules here; those belong in `AGENTS.md`. Historical incidents belong in `LEARNINGS.md`.

Release metadata rechecked: 2026-10-19 Sydney (2026-10-18 UTC).

## Production / release

- Latest stable GitHub/HACS release: **v4.10.0**, published 2026-09-05T09:08:34Z with `ovo_energy_au.zip`.
- Latest stable release target: `2a849bf007fa3f04c48cd385bc3a191a56f284e7`.
- Current `main` source version: **4.10.0**; no new product release is part of CI migration.
- Imported `main` head before Gitea tooling changes: `9f5212ab5f7892c7e86e9fe468ceb6cbcb013b4e` (`docs: make repository guidance Astra-ready`).
- Distribution: HACS resolves from the latest GitHub release; a version present only on `main` has not shipped to users.

## Supported runtime

- Home Assistant minimum advertised/enforced by HACS: **2026.8.3**.
- Python support: 3.11+; CI unit checks currently run on Python 3.12.
- Home Assistant runtime regressions currently run on Python 3.14 using `requirements-test-ha.txt`.
- Runtime dependency: `PyJWT>=2.13.0,<3.0.0`.
- Timezone authority: `Australia/Sydney`.

## CI gates

Personal migration preparation: private Gitea VM300 is the source of truth.
GitHub remains public for existing HACS distribution with Actions disabled.
The new `.gitea/workflows/ci.yml` preserves Ruff/full units/Python 3.14 HA
runtime/hassfest and creates a non-publishing POSIX candidate archive. It is
prepared but has not yet run. Official HACS validation is still a required
external release gate: its action needs a GitHub token and checks public GitHub
content rather than private Gitea source. No credential is transferred and no
HACS pass or release readiness is claimed. See `docs/gitea-release-route.md`.

The retained `.github/workflows/ci.yml` describes the original five gates;
GitHub Actions is disabled, so recovery pushes do not execute it:

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
