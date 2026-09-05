# OVO Energy Australia — agent operating guide

Home Assistant custom integration for OVO Energy Australia. Real users install releases through HACS, so changes must preserve compatibility, privacy and release integrity.

`AGENTS.md` is the canonical agent instruction file for this repository. `CLAUDE.md` points here for compatibility. Current release/runtime facts live in `STATUS.md`; historical incidents and expensive lessons live in `LEARNINGS.md`.

## Mission and risk

A mistake can break Home Assistant dashboards, long-term statistics, authentication or billing/usage displays for real users. The integration also handles a cleartext MyOVO password and account/vehicle PII.

The worst failure classes are:
- credentials, tokens, account IDs, NMI, addresses, VIN, GPS or vendor identifiers reaching logs, diagnostics or entity attributes;
- changing an entity key/unique ID and silently orphaning a user's history;
- publishing wrong energy, tariff or billing data that still looks plausible;
- turning an upstream outage/auth failure into a misleading healthy/empty state;
- releasing a version that was not tested against the exact source being shipped.

## Sources of truth

Use these in order:
1. code and tests in the current branch;
2. `STATUS.md` for volatile current state;
3. `LEARNINGS.md` for known failure modes and historical context;
4. `docs/guides/OVO_AU_API_DOCUMENTATION.md` for the mapped GraphQL surface;
5. `docs/legacy-agent-notes-2026-08-26.md` for deeper architecture/auth flow context.

Do not treat dates, versions, entity counts or test counts in old docs/issues as current unless verified.

## Architecture map

| Area | Primary files |
|---|---|
| Sensor definitions / keys | `custom_components/ovo_energy_au/sensors/definitions.py` |
| Sensor base behaviour / unique IDs | `custom_components/ovo_energy_au/sensors/base.py` |
| Vehicle sensors | `custom_components/ovo_energy_au/sensors/vehicle.py` |
| GraphQL queries | `custom_components/ovo_energy_au/graphql/queries.py` |
| Auth, refresh, GraphQL transport, rate limiting | `custom_components/ovo_energy_au/api.py` |
| Kaluza/EV client + privacy filtering | `custom_components/ovo_energy_au/vehicle.py` |
| Plan names, default rates, endpoints, intervals | `custom_components/ovo_energy_au/const.py` |
| Poll orchestration / source selection | `custom_components/ovo_energy_au/coordinator.py` |
| Config, options and reauth UI | `custom_components/ovo_energy_au/config_flow.py` + strings/translations |
| Diagnostics allow-list | `custom_components/ovo_energy_au/diagnostics.py` |
| Usage/rate analytics | `custom_components/ovo_energy_au/analytics/` |
| Version | `manifest.json`, `pyproject.toml`, README/info badges where applicable |

## Hard invariants

1. **Protect secrets and PII.** Never log or expose passwords, access/refresh tokens, raw account/user/device/optimisation IDs, NMI, addresses, VIN, coordinates, home-presence state or vendor certificate URLs. Recorder persists entity attributes to disk.
2. **Preserve entity identity.** `unique_id` is based on account ID plus sensor key. Treat sensor keys and device identifiers as persistent public API. Do not rename/remove them casually.
3. **Vehicle integration remains read-only.** Do not invoke or expose boost, schedule, charge-limit, unlink or other mutation actions without an explicit product decision.
4. **Kaluza auth is separate.** EV data uses a separate Kaluza/Firebase token chain. Do not send the normal MyOVO access token to Kaluza endpoints or gate vehicle discovery on `flex.hasOnboarded`.
5. **Never turn auth/transport failure into unexplained empty data.** Distinguish unavailable/retryable failures from valid empty results.
6. **Money is AUD dollars.** OVO commonly returns cents; convert deliberately. Per-kWh sensors retain four decimal places where required.
7. **All date/time maths uses `Australia/Sydney`.** Never depend on the host's local timezone or naive datetimes.
8. **`CREDIT` means solar export.** Every other charge direction is grid consumption unless a source-specific rule proves otherwise.
9. **Unclassified hourly tariff data remains `OTHER`.** Do not default unknown hourly rate data to shoulder/peak/off-peak; plan-window rebucketing depends on `OTHER`.
10. **A source snapshot is usable only after validation.** Do not let malformed/partial upstream responses overwrite last-known-good state or resolve incidents/usage implicitly.
11. **HACS ships releases, not `main`.** A source version bump without the corresponding GitHub release does not reach users.
12. **Release archives use POSIX paths.** Never build release ZIPs with Windows PowerShell 5.1 `Compress-Archive`; use the repository release workflow or Python/zip tooling that writes `/` entry paths.

## Execution contract

Infer routine implementation details from the task, repository patterns, tests and existing architecture. Bias toward completing the requested outcome rather than stopping for ordinary clarification.

Do not ask for confirmation for:
- reversible implementation details that are clear from existing patterns;
- regression tests required by the change;
- lint/format/type fixes caused directly by the change;
- related documentation updates;
- changes necessary to make the relevant CI checks pass.

Ask only when:
- alternatives have materially different product/user outcomes and intent cannot be inferred;
- the operation is destructive, irreversible or changes public compatibility intentionally;
- credentials/live-account access or unavailable external information is genuinely required;
- a security/privacy boundary would otherwise be crossed.

When given a bug or feature, continue through implementation and appropriate verification. Do not stop after producing an audit or partial patch unless the remaining work is externally blocked.

## Investigation rules

- Reproduce or trace the bug class before changing behaviour.
- Prefer root-cause fixes over string/exception matching or narrow trigger patches.
- Check adjacent code paths for the same failure mode, especially daily/monthly/yearly aggregation, import/export symmetry, setup/reauth/refresh flows and account/vehicle data.
- For upstream API assumptions, distinguish mapped/documented behaviour from inference.
- If real OVO verification is necessary, probes must be read-only and credentials must not be written to files, logs, CI, issues or commits.
- OVO usage normally arrives about a day late; missing today's data alone is not a bug.

## Verification policy

Match verification effort to change risk.

During implementation:
1. run the narrowest relevant regression tests first;
2. run Ruff/mypy or compilation checks for touched Python paths where useful;
3. fix failures attributable to the change;
4. avoid repeatedly running the full suite after every small edit.

Before merge:
- run the normal unit suite;
- run the Home Assistant runtime regressions for lifecycle/entity/setup changes;
- require Ruff, hassfest and HACS validation where CI provides them;
- add a regression test for each meaningful bug class fixed.

Before release:
- CI must pass for the exact source being released;
- version declarations must agree;
- release/tag must point to the intended tested commit;
- verify the published release asset when packaging changed.

Do not weaken or delete a valid failing test merely to get green CI. If a test encodes stale behaviour, update it only after proving the intended behaviour from current code/product requirements.

## Parallel work policy

Use parallel agents/tasks when they are genuinely independent, for example:
- auth review and analytics review;
- separate account/vehicle code paths;
- security/privacy review and test-gap review.

Do not parallel-edit the same small files or tightly coupled logic. The root agent owns integration, conflict resolution and final verification.

## Git and release discipline

- Work from the current remote `main`; re-check it before publishing if the task took long enough for the branch to drift.
- Prefer a review branch/PR for non-trivial changes.
- Do not force-push `main`.
- Keep release and workflow changes auditable.
- A `v*` tag/release is a shipping action. Do not create one unless the user asked to release or the task explicitly includes publication.
- If CI/release tooling is blocked externally, report the exact blocker; do not claim a release is verified when it is not.

## Instruction conflicts

User intent governs ordinary workflow choices, but the hard security/privacy/compatibility invariants above remain mandatory unless the user explicitly decides to change the product contract.

If another instruction file, skill or workflow rule prevents completion or requires confirmation:
1. identify the exact file/rule;
2. explain why it applies;
3. distinguish a hard requirement from an interpretation;
4. continue with all unblocked work rather than silently narrowing scope.

## Definition of done

A task is complete when the requested behaviour is implemented, relevant regressions exist, appropriate tests/checks pass, documentation/status is updated when the truth changed, and any requested GitHub publication step has been verified on the target branch/release.

## Context routing

Read only what the task needs:
- `STATUS.md` — current release, supported runtime, CI shape and current known operational state;
- `LEARNINGS.md` — expensive incidents; read before auth, vehicles, analytics, entity identity or release work;
- `docs/legacy-agent-notes-2026-08-26.md` — full Auth0 flow and deeper module map;
- `docs/guides/AUDIT_REPORT.md` — historical audit context, not guaranteed current;
- `docs/guides/OVO_AU_API_DOCUMENTATION.md` — mapped API surface;
- `docs/actions.md` — exposed Home Assistant action.
