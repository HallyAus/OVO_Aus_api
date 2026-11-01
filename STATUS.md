# Current status — OVO Energy Australia

Volatile project state for coding agents and maintainers. Update this file when release/runtime/CI truth changes. Do not put permanent engineering rules here; those belong in `AGENTS.md`. Historical incidents belong in `LEARNINGS.md`.

Release metadata rechecked: 2026-10-20 Sydney.

## PR #92 review — 2026-11-02 Sydney

- Reviewed the original contribution at `4fe5c65f7bb29d2ded56278943ddc46f239f559b`.
- Real Home Assistant reproductions confirmed sensor-class state handling made
  the new binary entity publish `unknown`, and clock boundaries did not publish
  tariff/price changes without a coordinator refresh. Corrected with a
  platform-neutral tariff base and entity-owned local time listeners.
- Preserved the explicit customer-local timezone fix from issue #86 and commit
  `64c417f2`; forcing Sydney globally would restore the Adelaide regression.
- Added binary-state, Free 3/Free 4 boundary, DST, interstate, timer lifecycle,
  zero-rate, privacy and malformed-rate regressions.
- The requested repository security cleanup also fixes credential forwarding
  through redirects, legacy token disclosure/retention, provider error leakage,
  malformed token cache updates and release-tool integrity failures.
- Final local verification: 358 integration/unit tests plus 24 offline tooling
  tests (24 additional subtests), 30 real-HA runtime tests on HA 2026.10.4, Ruff,
  production Bandit and official hassfest pass. Secret and external dependency
  scans are separate gates; the full HA dependency audit remains blocked below.
- Security remains a merge gate. The current official test harness
  (`pytest-homeassistant-custom-component==0.13.375`, HA 2026.10.4) pins
  Pillow 12.3.0, which fails the dependency audit; upstream fixes require 13.0.0.
  Do not suppress the advisories or override Home Assistant's exact core pins.
- New GitHub CI jobs explicitly check secrets, production source security,
  external package dependencies and the unmodified Home Assistant dependency
  set. Existing Ruff, unit, runtime, hassfest and HACS gates remain in place.
- These are review-branch changes, not a release. See
  `docs/reviews/pr92-tariff-security-review.md` for validation and the remaining
  dependency blocker.

## Production / release

- Latest stable GitHub/HACS release: **v4.10.0**, published 2026-09-05T09:08:34Z with `ovo_energy_au.zip`.
- Latest stable release target: `2a849bf007fa3f04c48cd385bc3a191a56f284e7`.
- Current release candidate version: **4.10.2**. It removes promotional content
  from Home Assistant and HACS dialogs while keeping support links in README.
- Imported `main` head before Gitea tooling changes: `9f5212ab5f7892c7e86e9fe468ceb6cbcb013b4e` (`docs: make repository guidance Astra-ready`).
- Distribution: HACS resolves from the latest GitHub release; a version present only on `main` has not shipped to users.

## Supported runtime

- Home Assistant minimum advertised/enforced by HACS: **2026.8.3**.
- Python support: 3.11+; CI unit checks currently run on Python 3.12.
- Home Assistant runtime regressions run on Python 3.14 using the compatible
  HA 2026.10.4 test harness pinned in `requirements-test-ha.txt`.
- Package dependency contract: standalone Python installs require
  `PyJWT>=2.15.1,<3.0.0` and `aiohttp>=3.14.4,<4.0.0`. The integration manifest
  leaves core-owned packages to Home Assistant rather than reinstalling or
  overriding its exact pins. The separate runtime dependency audit checks the
  actual supported Home Assistant environment.
- Timezone authority: customer-local HA configuration for live tariff windows;
  `Australia/Sydney` for existing OVO API parsing and historical aggregation.

## CI gates

Unpublished compatibility correction following the first private runner run:
official hassfest refused the duplicate core PyJWT manifest requirement and
warned that integration-level `async_setup` lacked a schema. The manifest now
leaves core PyJWT to HA, while `pyproject.toml` and the HACS minimum remain
unchanged; `CONFIG_SCHEMA` uses the official config-entry-only helper. No auth,
service, entity/lifecycle implementation, version, tag or release asset changed.
Focused metadata and real-HA schema/dependency regressions cover these contracts.

Official tagged evidence: [HA 2026.8.3 requirements](https://github.com/home-assistant/core/blob/2026.8.3/requirements.txt),
[HA 2026.9.1 requirements](https://github.com/home-assistant/core/blob/2026.9.1/requirements.txt)
and both releases' `homeassistant/package_constraints.txt` pin `PyJWT==2.13.0`.
The [2026.8.3 schema helper](https://github.com/home-assistant/core/blob/2026.8.3/homeassistant/helpers/config_validation.py)
explicitly covers integrations with `async_setup` and no YAML support. The
real-HA runtime test asserts the existing JWT range; a future HA dependency
change requires review rather than an automatic compatibility claim.

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
