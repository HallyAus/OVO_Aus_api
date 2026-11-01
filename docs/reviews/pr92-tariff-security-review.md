# PR #92: tariff correctness and repository security cleanup

Review date: 2 November 2026, Australia/Sydney.

Original contribution: [HallyAus/OVO_Aus_api#92](https://github.com/HallyAus/OVO_Aus_api/pull/92),
by rutj87, head `4fe5c65f7bb29d2ded56278943ddc46f239f559b`, based on
`d3ebf9de719547e15efeca491d5dad4e2a570430`.

## Merge decision

**The confirmed tariff and security defects have been corrected. Keep the
corrective PR #93 in draft until GitHub Actions is enabled and all hosted checks
pass for its final commit.** The dependency correction is a verified stable HA
security backport using the already merged upstream Pillow 13 change. Its
package metadata, runtime constraints and integration manifests agree, and the
normal resolver accepts it with the existing official test harness.

No vulnerability is ignored. The full actual inventory is audited, and the
verified official HA base is audited separately to prevent a custom version
label from hiding an upstream advisory. The test build is explicitly identified
as custom; it is not represented as an official HA release.

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
| Final integration/unit tests | 433 passed, including 75 source-build/audit regressions |
| Final offline release/recovery tools | 24 passed, plus 24 subtests |
| Combined unit/tool command | 457 passed, 24 subtests |
| Verified HA 2026.10.4 security backport / Python 3.14.8 | 40 passed; 23 tariff and 10 Pillow/version regressions added |
| Real HA 2026.9.0 earlier compatibility run | 30 passed before the broader auth cleanup |
| Ruff and patch whitespace | Passed |
| Production Python Bandit | Passed, zero findings |
| Repository secret hook | Passed; reviewed per-value public-provenance hash false positives, plus explicit non-secret public revision annotations |
| Resolved standalone external dependencies | Passed, 62 packages, zero known vulnerabilities |
| Dependency consistency | Both isolated unit and current HA environments pass `uv pip check` |
| Official hassfest | Passed: 1 integration, 0 invalid; all validators ran |
| HACS / final hosted GitHub checks | Pending: repository Actions is explicitly disabled; no hosted or HACS pass claimed |
| Corrected full HA dependency security | **Passed: 153 actual packages plus the verified upstream base; zero vulnerabilities and zero skips** |
| Installed HA artifact integrity | 14,563 original wheel files verified against the built artifact |
| Isolated build/scanner dependency security | Passed: 4 build packages, 28 scanner packages and patched setuptools 84.1.0; zero vulnerabilities or skips |

The synthetic HTTP security tests need permission for loopback sockets. The HA
runtime suite uses the real framework with mocked OVO transport. Clock tests stop
coordinator polling and assert unchanged API call lists across boundaries; they
also test entity unloading and exactly one callback after reload.

Production Bandit is clean. CLI/release tools retain ordinary unsuppressed low
severity subprocess/PATH warnings because they intentionally invoke Git, SSH and
the GitHub CLI. Their actual shell, argument, credential and provenance risks were
reviewed and regression-tested rather than hidden by scanner exclusions.

## Upstream dependency corrected in the test runtime

The original pinned test harness installed HA 2026.9.0 with 66 distinct advisory
IDs across aiohttp, cryptography, Pillow, PyJWT and uv. Moving to the latest
stable official harness fixed that set except Pillow:

`pytest-homeassistant-custom-component==0.13.375 → homeassistant==2026.10.4
→ Pillow==12.3.0`.

That unmodified stable environment had 152 packages and 39 distinct Pillow
advisories, all listing 13.0.0 as a fixed version. The original failing inventory
is preserved in `pr92-unpatched-runtime-dependency-audit.json`.

### Reproducible stable backport

The repository now carries a narrow backport of the already merged official
Pillow update. `scripts/build_ha_security_runtime.py`:

1. Downloads the exact official HA 2026.10.4 source commit
   `357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b` and verifies its SHA-256 before
   extraction. Archive extraction rejects unsafe paths, unexpected links and
   special files. Three known non-package documentation symlinks are omitted.
2. Verifies the checked-in upstream and derived patches by hash and file scope.
   The change comes from official HA commit
   `ae6f8602aab71b21505ff0974e7440fbff4aac21`. All 12 affected Pillow pins become
   `13.0.0`, including the eight affected integration manifests. The builder
   independently checks the precise expected contents after applying the patch.
3. Builds the explicitly labelled distribution
   `homeassistant==2026.10.4+ovo.pillow13.1` with pinned build tools. The derived
   patch also raises the isolated build backend from `setuptools==84.0.0` to
   `84.1.0`, fixing `GHSA-xmj3-9gf7-h52w`; the original source pin is separately
   verified before this explicit change. It preserves
   HA's internal calendar version `2026.10.4` and adds the discoverable
   `SECURITY_BACKPORT="ovo.pillow13.1"` marker. A local suffix on HA's internal
   version was tested and rejected because AwesomeVersion would classify it as
   semantic rather than calendar versioning and break upgrade comparisons.
4. Verifies the wheel's distribution identity, Pillow requirement, runtime
   constraints, manifests and backport marker. It records the exact wheel hash,
   source hashes, patch hashes and tool versions in `provenance.json`.

`requirements-test-ha.txt` pins this explicit custom version together with the
unchanged official fixture package. The normal resolver installs both and
`pip check` must succeed. Installation does not use dependency bypasses or
force an incompatible Pillow version into stock HA.

### Conservative auditing and compatibility

`scripts/audit_ha_security_runtime.py` collects the actual installed inventory,
verifies its backport provenance and rejects unexpected custom packages. It
runs a strict OSV audit of every installed distribution, plus a strict PyPI audit
of the verified upstream HA base. Both must succeed and report complete coverage
with no skipped packages or ignored advisories.

The additional base audit is necessary: positive controls found that adding a
local version suffix could omit an exact-boundary PyJWT advisory represented by
two database records, even though other advisories still made the scan fail.
Auditing the original official HA version conservatively prevents this class of
false green result.

The real-HA suite also exercises JPEG, PNG and GIF thumbnails, RGBA/LA/palette
conversion to JPEG, EXIF orientation, bounding-box/font rendering, the installed
Pillow version and HA's version-order comparisons. These tests address the
compatibility risk introduced by the major Pillow update in addition to the
original OVO entity regressions. Review of the official beta's corresponding
image calls found no additional Pillow-specific runtime adaptations required.

The final machine-readable inventory, both audit results and provenance are
recorded in `pr92-runtime-dependency-audit.json`. CI builds from the same pinned
source and executes the runtime suite in the exact environment it audits.
The isolated build frontend, scanner environment and exact build backend are
also audited with strict PyPI checks. The backend advisory concerns a legacy
installer path outside this PEP 517 build route, but its vulnerable pin was
removed to meet the complete dependency gate without exemptions.

### Scope and remaining hosted gate

This fixes the repository's Home Assistant test dependency. HACS distributes the
OVO integration; installing it does not upgrade Home Assistant core or Pillow in
an existing user's system. The integration itself has no Pillow imports or
image-processing path, and no PR-specific Pillow exploit has been demonstrated.
No live Home Assistant installation was accessed or upgraded during this work.
The custom wheel is a test artifact, not an official HA release or a claim that
all existing stock installations have been patched.

On 2026-11-02 Sydney, the repository's Actions settings visibly had **Disable
actions** selected. Default tokens were read-only and first-time fork runs
required approval. GitGuardian passed on the corrective PR, but normal CI and
HACS have no runs for its source. These missing hosted results remain a merge
gate; they are not reported as security test passes. The repository setting must
be enabled before final hosted verification can complete.

The temporary backport should be retired when a compatible official stable
HA/test-harness combination includes patched Pillow. Its replacement must pass
normal dependency resolution, the complete audit and the real runtime suite.

Primary evidence:

- [Stable HA package metadata](https://pypi.org/pypi/homeassistant/2026.10.4/json)
- [Stable HA runtime constraints](https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/package_constraints.txt)
- [Official test harness](https://pypi.org/project/pytest-homeassistant-custom-component/0.13.375/)
- [Pillow 13 security release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html)
- [Critical multi-frame advisory](https://github.com/python-pillow/Pillow/security/advisories/GHSA-v9pv-5gc8-w2m6)
- [Upstream HA Pillow update](https://github.com/home-assistant/core/commit/ae6f8602aab71b21505ff0974e7440fbff4aac21)
- [Setuptools build-tool advisory and patched version](https://github.com/pypa/setuptools/security/advisories/GHSA-xmj3-9gf7-h52w)
- [Setuptools path-containment fix and affected invocation path](https://github.com/pypa/setuptools/commit/6d07b8d17890dda58d944ac51e58f54af92d52af)
- [pip-audit supported audit services and strict mode](https://github.com/pypa/pip-audit)
