<!-- learnings-file: v1 · cap: 40 entries · archive: docs/learnings-archive-<year>.md -->
# Learnings — OVO Energy Australia (HA integration)

Append-only. Newest first. Never edit an existing entry; supersede it with a new one.
Every entry must name a cost. No cost, no entry.

---

## 2026-08-20 — Vehicles silently absent: the Kaluza endpoint needs its own sign-in
**Cost:** A second full authenticated read-only probe of the live OVO platform, plus a third patch
release (v4.8.2) two days after the feature shipped. Users with a connected EV saw nothing and got no error.
**What happened:** v4.8.0 shipped "complete connected-vehicle support". On a real enrolled vehicle it
returned an empty set. Nothing logged a failure — the entities simply never appeared.
**Root cause:** The implementation sent the normal MyOVO access token to the account-scoped
Firebase/Kaluza token endpoint. That endpoint requires its own separate Kaluza OAuth sign-in first.
The initial platform map was wrong about this, and the failure path returned an empty list rather than raising.
**Fix applied:** Implemented the portal's real two-stage MyOVO → Kaluza PKCE chain; cached Kaluza tokens
and preferred their refresh tokens, falling back to the password/SSO path only when no usable refresh
token remains. Vehicle auth failure now emits one clear warning, reports `vehicle_status` in diagnostics,
and drops to debug on repeat.
**Rule now in AGENTS.md:** "EV data comes from a separate Kaluza/Firebase token chain, account-scoped —
NOT the MyOVO access token." Plus: never return an unexplained empty set from an auth path.
**Recurrence guard:** Regressions in `tests/test_vehicle.py` covering Kaluza SSO parameters,
refresh-first token reuse, account-to-customer matching, and `vehicle_status` reporting.

## 2026-08-19 — `flex.hasOnboarded` is the wrong flag; it hid all 19 vehicle entities
**Cost:** A same-day emergency patch release (v4.8.1) hours after v4.8.0.
**What happened:** Vehicle discovery was gated on the GraphQL `flex { hasOnboarded }` field. On an
account with a valid EV Control vehicle the flag was false, so every one of the 19 vehicle entities was skipped.
**Root cause:** `flex.hasOnboarded` describes MyOVO **Flex** onboarding — a separate product state —
and says nothing about EV Control enrolment. The two were assumed to be the same thing because both
sit under the same account.
**Fix applied:** Removed the flag from the discovery condition entirely.
**Rule now in AGENTS.md:** Listed under Traps — "`flex.hasOnboarded` describes MyOVO Flex, not EV Control."
**Recurrence guard:** Test asserting vehicle discovery succeeds when the unrelated Flex flag is false.

## 2026-08-19 — v4.8.0 collapsed ~281 entities onto one device
**Cost:** Same-day patch release (v4.8.1); users' device-based dashboard cards and filters broke on upgrade.
**What happened:** A device-grouping change merged approximately 281 entities onto the single account
device, destroying the category devices (Yesterday, This Month, Analytics, …) users organise dashboards around.
**Root cause:** The account device was introduced as the parent without preserving the existing
per-category device identifiers.
**Fix applied:** Restored category-specific devices, keeping the account device as their parent.
**Rule now in AGENTS.md:** Danger zone — entity/device identity changes break user dashboards and history.
**Recurrence guard:** Test covering category device identifiers.

## 2026-07-17 — v4.7.1 was bumped but never tagged, so no user ever received it
**Cost:** Three real user-facing fixes (4-decimal per-kWh rates, multi-account balance, reauth error
mapping) sat invisible for ~33 days until they were folded into v4.8.0 on 2026-08-19.
**What happened:** The version was bumped in the source files and committed to `main`, but no GitHub
release was created. `gh release list` still shows no `v4.7.1`.
**Root cause:** HACS resolves the installable version from the **latest GitHub release tag**, not from
`main`. A version bump on `main` is completely invisible to users; nothing warns you.
**Fix applied:** The fixes were re-shipped inside v4.8.0. The release process was written down as a
mandatory 7-step checklist ending in a `gh release list` verification.
**Rule now in AGENTS.md:** Rule 1 — "A version bump without a GitHub release ships nothing."
**Recurrence guard:** none — manual discipline. The `release.yml` workflow now also accepts
`workflow_dispatch` with a tag input, so a release can be cut even when tags cannot be pushed directly.

## 2026-06-14 — `Compress-Archive` produced a manual-install zip that was broken on Linux/macOS
**Cost:** A re-uploaded release asset; every user who downloaded the manual-install zip in between got
an unusable archive.
**What happened:** The release zip built on Windows PowerShell 5.1 extracted as a single mangled
filename (`ovo_energy_au\sensors\definitions.py`) on Linux and macOS, where most Home Assistant users run.
**Root cause:** Windows PowerShell 5.1's `Compress-Archive` writes entry paths with backslash
separators. Windows tolerates it; the zip spec requires forward slashes, so POSIX extractors treat the
whole path as one filename.
**Fix applied:** Build the zip with Python's `zipfile`, forcing forward-slash relative paths and
skipping `__pycache__`/`.pyc`. The exact command is in `docs/legacy-agent-notes-2026-08-26.md`.
The `release.yml` workflow uses `zip -r`, which is already correct.
**Rule now in AGENTS.md:** Rule 2 — never use PowerShell `Compress-Archive` for the release zip.
**Recurrence guard:** none — manual discipline. Verify asset entries after upload.

## 2026-06-14 — Unclassified hourly data defaulted to "shoulder" and silently killed the Free-3 split
**Cost:** Issues #63 and #74; the Free-3 peak/off-peak breakdown was wrong on real accounts while
passing tests, and needed release v4.2.2 to fix.
**What happened:** The Free 3 plan's peak/off-peak window split produced no result on live data even
though the logic was correct in isolation.
**Root cause:** OVO's hourly API returns `rates: null` **and** `charge: null` on some accounts, so
there is no per-hour rate signal at all. The parser fell back to the entry-level `charge.type`, which
is only a DEBIT/CREDIT direction — never a TOU rate — and mapped `DEBIT` to `shoulder`. The re-bucketing
step (`_split_other_by_window`) only touches entries labelled `OTHER`, so it never saw them.
**Fix applied:** Unclassified hours are now labelled `OTHER` so the window split can re-bucket them.
The reasoning is preserved as a comment in `analytics/hourly.py`.
**Rule now in AGENTS.md:** Listed under Traps.
**Recurrence guard:** Regression tests in `tests/test_analytics.py` / `tests/test_hourly_helpers.py`
exercising the null-rates path.
