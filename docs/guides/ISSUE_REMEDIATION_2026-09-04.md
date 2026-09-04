# GitHub issue remediation — 2026-09-04

Scope: open issues #77, #78, #79, #80 and #82, plus the documentation follow-up
promised when #81 was closed. This report records the evidence, implementation,
and verification for the unreleased v4.9.1 worktree. It contains no account,
meter, vehicle, credential, token, address, or location data.

## Results

| Issue | Root cause | v4.9.1 remediation |
|---|---|---|
| [#77](https://github.com/HallyAus/OVO_Aus_api/issues/77) | Category and vehicle entities referenced an account `via_device` whose creation depended on entity setup order. | Integration setup now creates the account device explicitly before forwarding sensor platforms and gives child devices its unambiguous `via_device_id`. |
| [#78](https://github.com/HallyAus/OVO_Aus_api/issues/78) | Free 4 was neither a recognised plan nor a supported rate-bucket spelling; existing entries also retained their setup-time plan after an OVO plan switch. | Added Free 4/Basic Free 4 detection, the fixed 11am-3pm window, contractual $0 enforcement, `FREE_4` usage support, irrelevant EV-rate filtering, active-agreement selection, and refresh-driven plan/rate changes unless the user deliberately set an override. |
| [#79](https://github.com/HallyAus/OVO_Aus_api/issues/79) | The tariff indicator treated the existence of a super-off-peak field as a free plan feature and previously exposed EV placeholders on unrelated plans. | Plan type now gates EV/free features. A non-zero One Plan super-off-peak rate is labelled paid Super Off-Peak and uses the live API price for the reported 11am-4pm window. |
| [#80](https://github.com/HallyAus/OVO_Aus_api/issues/80) | v4.8.2 registered moving Day 1-7 entities that had generated statistics and then stopped declaring a state class. | v4.9 already retired and registry-cleans all 161 moving day/hour entities. v4.9.1 documents the one-time Home Assistant action for deleting any remaining orphaned statistics; they cannot be meaningfully migrated because each old ID represented a different date every day. |
| [#82](https://github.com/HallyAus/OVO_Aus_api/issues/82) | Current Tariff Period applied only fixed free/EV windows and ignored the configured peak window. | The configured half-open, overnight-capable peak window now drives Peak/Off-Peak labels, live/configured rates, the next transition, and the existing hourly `OTHER` split. |
| [#81](https://github.com/HallyAus/OVO_Aus_api/issues/81) | The README and HACS metadata still advertised 2024.6 although a 2026.6.2 Container installation could not resolve the pinned PyJWT requirement. | The README and HACS minimum now match the reporter-verified working release, Home Assistant 2026.8.3. |

## Product evidence

- OVO's [Free 4 product page](https://pages.ovoenergy.com.au/the-free-4-plan)
  specifies free eligible usage from 11am to 3pm daily.
- OVO's [legacy Free 3 product page](https://pages.ovoenergy.com.au/the-free-3-plan)
  specifies free eligible usage from 11am to 2pm daily.
- OVO's [EV product page](https://pages.ovoenergy.com.au/the-ev-plan) specifies
  EV off-peak from midnight to 6am.
- The #79 reporter supplied their United Energy tariff table and live product
  prices: paid super-off-peak from 11am to 4pm, with no EV period.
- Home Assistant's [sensor documentation](https://developers.home-assistant.io/docs/core/entity/sensor/)
  confirms that state classes opt entities into long-term statistics. The
  retired moving-label entities are deliberately not restored because doing so
  would resume recording a semantically invalid time series.

OVO does not return every distributor-specific peak boundary in the queried
product agreement. Fixed product windows are automatic; peak start/end remains
configurable and is now used consistently by both the current-period entity and
hourly analytics. For a paid midday super-off-peak period, a configured
afternoon peak start also becomes the end of that midday period; 4pm remains the
fallback for the United Energy structure reported in #79.

## Independent double-check

The final adversarial pass re-read every issue body and comment, reviewed the
implementation against the Home Assistant 2026.8.3 device-registry API, and
exercised all 24 hours of the reported United Energy One Plan schedule. It found
and corrected four gaps before release:

1. A non-zero generic `superOffPeak` placeholder could contradict a Free 3/Free
   4 label; contractual free periods now always return zero.
2. Product selection assumed the first agreement was current; it now selects
   the latest active agreement and refreshes automatically managed rates.
3. Identifier-based `via_device` is deprecated in the declared minimum Home
   Assistant version; child devices now use the created parent's device ID.
4. Multi-account contact lookup could fall back to another active account when
   no exact match existed; the fallback was removed.

## Verification

- `python -m pytest tests/ -q`: 169 passed.
- `ruff check custom_components/ovo_energy_au/ tests/`: passed.
- `python -m compileall -q custom_components tests`: passed.
- Pre-commit JSON, YAML, whitespace, merge-conflict, large-file, Ruff, and
  detect-secrets checks: passed after the final review.
- `git diff --check`: passed.

The test environment mocks Home Assistant and is not a substitute for loading
the release on a real HA 2026.8.3 instance. No GitHub issues were closed and no
release was published while preparing this report.
