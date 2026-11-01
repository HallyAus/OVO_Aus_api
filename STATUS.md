# Current status — OVO Energy Australia

Volatile project state for coding agents and maintainers. Update this file when release/runtime/CI truth changes. Do not put permanent engineering rules here; those belong in `AGENTS.md`. Historical incidents belong in `LEARNINGS.md`.

Release metadata rechecked: 2026-11-02 Sydney.

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
- Security remains a merge gate. The original stable HA 2026.10.4 pins Pillow
  12.3.0. The test runtime now builds a labelled stable security backport,
  `homeassistant==2026.10.4+ovo.pillow13.1`, with the official upstream Pillow 13
  change applied consistently to all 12 affected dependency locations.
  The original official test harness remains at 0.13.375. Normal dependency
  resolution must succeed; no conflicting package is forced into the runtime.
  The isolated backend is explicitly patched to `setuptools==84.1.0` for
  `GHSA-xmj3-9gf7-h52w`; build and scanner dependency graphs are also audited.
- The build verifies immutable source/patch provenance. Full installed-package
  OSV auditing is supplemented with a conservative PyPI audit of the verified
  upstream HA base, so a custom version label cannot hide an upstream advisory.
  Audit coverage must equal the inventory with zero skips or ignored findings.
- New GitHub CI jobs explicitly check secrets, production source security,
  external package dependencies and the actual patched Home Assistant dependency
  set. Existing Ruff, unit, runtime, hassfest and HACS gates remain in place.
- Final local verification: 457 unit/tool tests plus 24 subtests, 40 real-HA
  regressions, production Bandit, Ruff, secret scanning and official hassfest
  pass. The corrected runtime audit covers all 153 installed distributions
  plus the verified upstream base, with zero known vulnerabilities or skips.
- These are review-branch changes, not a release. See
  `docs/reviews/pr92-tariff-security-review.md` for exact validation results.

## Production / release

- Latest stable GitHub/HACS release: **v4.10.2**, published 2026-10-20T07:37:35Z with `ovo_energy_au.zip`.
- Latest stable release target: `eb201cfe3c5063feff56f3b14c4ce2cd9d3f19cb`.
- Current source version: **4.10.2**. The published release removes promotional content
  from Home Assistant and HACS dialogs while keeping support links in README.
- Main rechecked at `d3ebf9de719547e15efeca491d5dad4e2a570430`; review work is on
  `fix/pr92-tariffs-security-review` in corrective PR #93, retaining PR #92's
  contributor commit. No new release or merge has been performed.
- Distribution: HACS resolves from the latest GitHub release; a version present only on `main` has not shipped to users.

## Supported runtime

- Home Assistant minimum advertised/enforced by HACS: **2026.8.3**.
- Python support: 3.11+; CI unit checks currently run on Python 3.12.
- Home Assistant runtime regressions run on Python 3.14 using the explicit
  2026.10.4 security backport and official fixture dependency pinned in
  `requirements-test-ha.txt`. The distribution carries its custom version;
  HA's internal calendar version remains the stable base for version guards.
- Package dependency contract: standalone Python installs require
  `PyJWT>=2.15.1,<3.0.0` and `aiohttp>=3.14.4,<4.0.0`. The integration manifest
  leaves core-owned packages to Home Assistant rather than reinstalling or
  overriding its exact pins. The separate runtime dependency audit checks the
  actual test environment. HACS installation does not update Home Assistant core
  or repair Pillow in an existing installation; this test build is not an
  official HA release or a deployment to users.
- Timezone authority: customer-local HA configuration for live tariff windows;
  `Australia/Sydney` for existing OVO API parsing and historical aggregation.

## CI gates

GitHub is canonical under the 2026-10-22 policy in `AGENTS.md`. The retired
Gitea/recovery scripts are retained for offline verification only; no former
hosting or deployment route was reactivated.

The repository's Actions settings were directly inspected on 2026-11-02 Sydney:
**Disable actions** is selected. Default workflow-token permissions are read-only,
first-time fork contributors need approval, and Actions cannot approve PRs.
The corrective PR has a successful GitGuardian secret check, but GitHub Actions
cannot execute the following required gates while Actions is disabled:

1. Ruff lint.
2. Unit/packaging tests.
3. Official Home Assistant hassfest.
4. Official HACS integration validation.
5. Actual Home Assistant runtime regressions, including tariff and Pillow checks.
6. Secrets, production Python security, offline tools and external dependencies.
7. Exact Home Assistant dependency audit and conservative upstream-base audit.

CI uses hosted runners, read-only tokens, immutable action revisions and
validator images. Release verification refuses publication unless every named
job succeeded in the latest main-push run for the exact source SHA. Local checks
do not substitute for missing hosted CI or HACS results.

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
