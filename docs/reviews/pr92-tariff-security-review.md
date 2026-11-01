# PR #92: tariff correctness and repository security cleanup

Review date: 2 November 2026, Australia/Sydney.

Original contribution: [HallyAus/OVO_Aus_api#92](https://github.com/HallyAus/OVO_Aus_api/pull/92),
by rutj87, head `4fe5c65f7bb29d2ded56278943ddc46f239f559b`, based on
`d3ebf9de719547e15efeca491d5dad4e2a570430`.

## Merge decision

**Keep the corrected contribution in draft until the full runtime dependency
security gate and the final GitHub checks pass.** The confirmed tariff defects
and repository security issues described below are corrected and covered by
regressions. The current stable Home Assistant dependency set still includes
vulnerable Pillow 12.3.0. No advisory is suppressed and no Home Assistant pin is
overridden to manufacture a passing result.

The review branch retains the contributor's feature commit and adds corrections.
It does not publish a release or install anything into a user's Home Assistant.

## Original tariff failures and corrections

### Binary state resolution

The original method resolution order is:

`OVOFreeEnergyWindowBinarySensor → OVOBaseSensor → CoordinatorEntity →
BaseCoordinatorEntity → SensorEntity → BinarySensorEntity → Entity`.

The first implementation of `state` is therefore `SensorEntity.state`. At Sydney
noon on Free 3, the original object has `is_on=True` but `state=None`; real Home
Assistant publishes `unknown`. This was reproduced with actual HA 2026.9.0,
not reconstructed entity stubs. The original 213 mocked unit tests still pass.

The corrected shared `OVOTariffEntity` is platform-neutral. The binary class
inherits `BinarySensorEntity` without `SensorEntity` anywhere in its ancestry.
The existing tariff-period and new price entities reuse the same coordinator and
clock behaviour while retaining their unique IDs and account device identifiers.

### Clock transitions

The original contribution has no clock listener. With coordinator polling
disabled, its published import price remains 0.2574 AUD/kWh when the clock crosses
11:00. The corrected binary, price and period entities register local whole-hour
listeners, publish their states without an API request and cancel their listeners
on removal. Every currently supported tariff boundary is a whole local hour.

Home Assistant deliberately staggers these timer callbacks by approximately
0.05–0.5 seconds. This is normal scheduler latency, independent of the former
five-minute polling delay. These are software scheduling tests, not a guarantee
of appliance actuation latency or behaviour while Home Assistant is stopped.

| Plan | Before 11:00 | At 11:00 | At 14:00 | At 15:00 |
|---|---|---|---|---|
| Free 3 | off, ordinary rate | on, zero rate | off, ordinary rate | off |
| Free 4 | off, ordinary rate | on, zero rate | on, zero rate | off, ordinary rate |

The window is start-inclusive and end-exclusive. A zero ordinary rate does not
activate the dedicated window sensor. `hours_remaining` now includes minutes
and seconds and is a snapshot at the latest entity update.

### Timezone assessment

An implicit `dt_util.now()` is not an operating-system-clock defect: Home
Assistant supplies its configured timezone. A Sydney installation must use
`Australia/Sydney`, which follows DST automatically.

Hardcoding Sydney for every installation would undo the maintainer's deliberate
[issue #86 correction](https://github.com/HallyAus/OVO_Aus_api/commit/64c417f2f6b24481db28677f9daf7d5379c9e954).
That issue documents an Adelaide customer's free period ending 30 minutes early.
This review preserves customer-local tariff clocks, tests Sydney summer/winter
and both DST changes, and protects Adelaide and Brisbane behaviour. Stale guidance
was clarified; existing API/history aggregation conventions were retained.

Official [OVO NSW special terms](https://www.ovoenergy.com.au/terms/nsw/special-terms/)
specify Free 3 from 11am to 2pm and Free 4 from 11am to 3pm.

## Repository security cleanup

These additional findings predate the contribution and were included after the
maintainer explicitly requested a repository security cleanup before merge.

| Confirmed issue | Correction and evidence |
|---|---|
| Fixed secret-bearing endpoints followed redirects; custom ID-token headers and 307/308 request bodies could reach another origin. | Disable redirects and reject 3xx on login, token, GraphQL and authenticated vehicle requests. Real aiohttp tests use two loopback servers and synthetic credentials. |
| Login HTML could select an unrelated form destination for an authentication ticket. | Require the configured HTTPS issuer origin before submitting the form. Legitimate SSO redirects remain supported. |
| Diagnostics exposed OAuth tokens persisted by older integration versions. | Recursively redact access, identity and refresh token fields; successful reauthentication retires the obsolete persisted values. |
| OAuth error descriptions and chained transport exceptions exposed provider context. | Use static public errors and suppress sensitive external exception chains. |
| Invalid token lifetimes could partly replace credentials or overrun cache expiry. | Validate complete token responses before mutation; reject malformed values and bound proactive cache lifetimes. |
| Malformed vehicle response roots were interpreted as valid empty data. | Report a communication failure; genuine optional HTTP 404 remains supported. |
| Package version floors still permitted versions with published advisories. | Raise standalone aiohttp and PyJWT floors to patched versions and audit the full resolved external inventory. Core-owned HA packages remain under HA's dependency contract. |
| Actions, hooks and validator containers used mutable references. | Pin verified upstream commits and OCI digests, remove persisted checkout credentials and monitor image updates with Dependabot. |
| Release verification accepted an older successful run without requiring named security jobs. | Require the latest successful main-push run for the exact SHA and explicit success of every CI/security job. Missing, skipped, failed or cancelled jobs fail closed. |
| Existing tags and working-tree ZIP packaging could disagree with tested source. | Verify HEAD and tag commit targets, reject non-commit tags, and build immutable POSIX ZIPs from regular tracked Git blobs only. |
| Retained release/recovery scripts had unsafe shell-path interpretation, incomplete gates and insufficient archive/receipt validation. | Quote and validate SSH inputs, scrub child credentials, require all named gates, reject unsafe member metadata before decompression and create receipts exclusively. Tests are offline; retired workflows remain inactive. |

The redirect reproductions show conditional disclosure under controlled redirect
responses. They do not establish that OVO emitted such a redirect or that anyone's
real credentials were exposed. No live OVO account or vehicle control was used.

## Validation

| Gate | Result |
|---|---|
| Original unit baseline | 213 passed, despite confirmed runtime failures |
| Original real-HA reproduction subset | 7 failed: incorrect binary state/MRO and stale price at the boundary |
| Final integration/unit tests | 358 passed |
| Final offline release/recovery tools | 24 passed, plus 24 subtests |
| Combined unit/tool command | 382 passed, 24 subtests |
| Real HA 2026.10.4 / Python 3.14.8 | 30 passed; 23 newly added tariff regressions |
| Real HA 2026.9.0 earlier compatibility run | 30 passed before the broader auth cleanup |
| Ruff and patch whitespace | Passed |
| Production Python Bandit | Passed, zero findings |
| Repository secret hook | Passed; existing baseline false positives only, plus explicit non-secret public revision annotations |
| Resolved standalone external dependencies | Passed, 62 packages, zero known vulnerabilities |
| Dependency consistency | Both isolated unit and current HA environments pass `uv pip check` |
| Official hassfest | Passed: 1 integration, 0 invalid; all validators ran |
| HACS / final hosted GitHub checks | Require the final published ref and normal GitHub Actions execution; no local pass claimed |
| Current stable HA dependency security | **Failed: 39 distinct Pillow advisories** |

The synthetic HTTP security tests need permission for loopback sockets. The HA
runtime suite uses the real framework with mocked OVO transport. Clock tests stop
coordinator polling and assert unchanged API call lists across boundaries; they
also test entity unloading and exactly one callback after reload.

Production Bandit is clean. CLI/release tools retain ordinary unsuppressed low
severity subprocess/PATH warnings because they intentionally invoke Git, SSH and
the GitHub CLI. Their actual shell, argument, credential and provenance risks were
reviewed and regression-tested rather than hidden by scanner exclusions.

## Remaining upstream dependency blocker

The old pinned test harness installed HA 2026.9.0 with 66 distinct advisory IDs
across aiohttp, cryptography, Pillow, PyJWT and uv. Updating to the latest stable
official harness removes every affected package from that set except Pillow:

`pytest-homeassistant-custom-component==0.13.375 → homeassistant==2026.10.4
→ Pillow==12.3.0`.

The current environment has 152 packages and 39 distinct Pillow advisories. All
have 13.0.0 listed as a fixed version. The integration has no Pillow imports or
image-processing path; a PR-specific Pillow exploit has not been demonstrated.
The full runtime audit remains a required failing gate under the requested
security standard.

Primary evidence:

- [Stable HA package metadata](https://pypi.org/pypi/homeassistant/2026.10.4/json)
- [Stable HA runtime constraints](https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/package_constraints.txt)
- [Official test harness](https://pypi.org/project/pytest-homeassistant-custom-component/0.13.375/)
- [Pillow 13 security release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html)
- [Critical multi-frame advisory](https://github.com/python-pillow/Pillow/security/advisories/GHSA-v9pv-5gc8-w2m6)
- [Upstream HA Pillow update](https://github.com/home-assistant/core/commit/ae6f8602aab71b21505ff0974e7440fbff4aac21)

The upstream fix exists in HA 2026.11.0b0/b1. Those are prereleases; no matching
published official test harness exists yet. Every stable HA version from this
integration's existing minimum through 2026.10.4 still pins Pillow 12.3.0.
A resolver dry run confirms stable HA plus Pillow 13 has incompatible requirements.

To clear the remaining gate, update to a released stable HA/test-harness pair
that includes patched Pillow, then rerun dependency consistency, the full audit,
runtime regressions and hosted CI. Do not force a conflicting Pillow pin or
suppress the findings. The exact current dependency inventory and advisory IDs
are recorded in `pr92-runtime-dependency-audit.json` beside this report.
