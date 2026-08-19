# OVO Energy Australia integration audit

**Audit date:** 19 August 2026

**Code baseline:** manifest/source version 4.7.1 / `c3bb4df`

**Latest GitHub release during audit:** v4.7.0

**Scope:** complete repository, Home Assistant integration lifecycle, Auth0/API
client, GraphQL coverage, sensors and analytics, config/reauth/options flows,
privacy, tests, blueprints, installers, translations, documentation, and a
read-only authenticated probe of the current MyOVO/Flex web platform.

No credential, token, account number, NMI, address, bill URL, vehicle ID, VIN,
balance, payment detail, or customer-specific value is stored in this report.
The temporary browser credential profile and authenticated session were deleted
after the probe.

## Outcome

The integration was functional and its analytics test suite was healthy, but the
audit found correctness, privacy, lifecycle, load, documentation, and test gaps.
The coordinated remediation resolves the actionable defects listed below and
adds the useful billing and privacy-filtered connected-vehicle surfaces
confirmed by the live portal.

The project was first fast-forwarded to the 4.7.1 source baseline, which already
fixed per-kWh precision, multi-account balance matching, and invalid-auth error
mapping. That source version had not yet been published as the latest GitHub
release during the audit.

## Live platform map

The current MyOVO portal uses Auth0 authorization-code flow with PKCE and a
GraphQL API at `my.ovoenergy.com.au/graphql`. A read-only route sweep observed
these operations:

- Account: `GetAccountContacts`, `GetContactInfo`, `GetUsageInfo`
- Usage/plan: `GetIntervalData`, `GetHourlyData`, `GetProductAgreements`
- Billing: `GetBillingInformation`, `GetPaymentDetails`, `GetStatements`,
  `GetUnbilledCharges`
- Other: `GetFlex`, `GetRafTotalEarned`, `GetConcession`, `GetLifeSupport`

The integration already covered usage, plan, statements, payments, referrals,
account balance, and Flex onboarding. This remediation adds a deliberately
minimal billing query for direct-debit and unbilled-charge summaries. It does
not request masked bank/card/BPAY identifiers from `GetPaymentDetails`.

### Separate Kaluza Flex surface

The EV Control route also revealed a distinct Kaluza/Firebase surface:

- account-scoped token exchange;
- vehicle/device registration and telemetry;
- charge plan and charging-time endpoints;
- monthly EV energy-consumption documents.

Those responses include control-adjacent data plus vehicle state, location/home
flags, VIN, and device identifiers. A second read-only sweep of the EV dashboard,
charge-limit, charging-time, demand-period, and solar-status routes confirmed the
complete GET contract and did not invoke any write/control action.

The implementation now covers registration/readiness, live telemetry, charging
preferences, all charge-plan intervals, charging-time and demand-period settings,
monthly EV kWh/cost/rate/source detail, and vendor credential health. Raw
account/user/device and optimisation IDs, VIN, coordinates/home-presence flags,
tokens, tariff IDs, and certificate-install URLs are discarded before data
reaches the coordinator. Stable Home Assistant device identifiers use a one-way
hash. Remote charging/settings/removal actions remain outside the verified and
safe boundary.

## Resolved findings

### Authentication and transport

- OAuth `state` was generated but not checked at callback; it is now compared in
  constant time before code exchange.
- OIDC `nonce` was generated but not checked; the returned ID-token nonce is now
  validated before tokens are accepted.
- Five-minute token rotation preferred resubmitting the password. Refresh tokens
  are now used first, with credential login only after an explicit refresh-token
  rejection.
- Request throttling used wall-clock time and could misbehave after clock jumps;
  it now uses `time.monotonic()`.
- PyJWT's minimum was stale. The integration now requires the current 2.13 line
  with a `<3` compatibility bound.

### Home Assistant lifecycle and configuration

- Runtime coordinator storage now uses `ConfigEntry.runtime_data`.
- `refresh_data` is registered once from integration-level `async_setup`, not
  per config entry, and is documented as an action.
- Plan settings are now stored in config-entry options. An entry update listener
  reloads the integration after changes without requiring Home Assistant's newer
  `OptionsFlowWithReload` helper; existing data-based settings remain readable.
- The initial EV fallback rate now matches the model/default-rate value.
- A privacy-safe diagnostics module was added.

These changes follow current Home Assistant guidance for
[runtime data](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/runtime-data/),
[action setup](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-setup/),
and [options reload](https://developers.home-assistant.io/docs/core/integration/options_flow/).

### Data correctness

- The bill estimate subtracted a solar-generation charge rather than the actual
  return-to-grid credit. It now uses `return_to_grid_charge`.
- “Last 7 Days” hourly totals could include an eighth day or partial current day.
  Hourly processing now applies an AU-local half-open seven-day window.
- The tariff-period sensor claimed EV/free schedules and hard-coded rates for all
  plan types. It now activates only periods supported by the detected plan/API
  rates and uses live plan rates with configured fallbacks.
- Moving “day N” and “N days ago” entities were eligible for long-term
  statistics despite changing calendar dates. Their state class is now unset.
- Live direct-debit amount, minimum amount, unbilled electricity, unbilled solar,
  and bill-progress sensors were added from fields confirmed in MyOVO.

### Privacy and resource use

- Account IDs and NMIs were removed from Recorder-visible diagnostic attributes.
- Signed bill download URLs were removed from entity attributes and recent-bill
  history.
- Account entities retain category-specific devices linked to one parent account
  device, keeping the large entity set navigable without exposing account IDs
  as Recorder attributes.
- Detailed daily/hourly history entities remain available but start disabled to
  reduce Recorder, registry, and update load. This follows Home Assistant's
  [disabled-by-default guidance](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-disabled-by-default/).
- The local `reference/` directory is ignored to prevent accidental commits of
  customer statements or research artifacts.
- Connected vehicles are represented as their own physical devices, linked to
  the OVO account device. Diagnostics expose only vehicle/telemetry/plan/energy
  availability counts; detailed schedule attributes contain no raw identifiers.

### Connected vehicles

- A dedicated Kaluza/Firebase client follows the portal's short-lived token
  chain, caches the token within its lifetime, retries once after rejection, and
  uses only GET requests.
- Multi-vehicle discovery is supported, including vehicles that appear after
  integration setup.
- Vehicle discovery is independent of the unrelated `flex.hasOnboarded` flag;
  a false Flex value cannot suppress an EV Control vehicle.
- Nineteen entities per vehicle expose automation-friendly battery, range,
  cable, mode, boost, charge-limit, timestamp, power, SOC, energy and cost
  values plus complete privacy-safe status, preferences, schedule and charge
  plan attributes.
- The current-month Firestore energy document is decoded recursively and
  preserves daily periods, rate categories, costs and energy-source mixes.

### Documentation, packaging, and UX

- PowerShell no longer downloads an obsolete branch; it uses the latest release
  asset. Local-copy paths in both installers now resolve from the repository root.
- Installer output and the HACS/quick-start guides no longer instruct users to
  extract JWTs or configure unsupported YAML.
- Historical reverse-engineering documents now carry explicit token-safety and
  non-installation warnings; the raw authorization-header format is corrected.
- The notification blueprint now defaults to
  `persistent_notification.create` and uses modern action syntax.
- Billing-cycle option text is present in every bundled translation.
- Sensor-count marketing was replaced with accurate core/optional wording.

## Validation

- `python -m pytest tests -q`: **134 passed**
- `python -m ruff check custom_components/ovo_energy_au tests`: **passed**
- Python bytecode compilation: passed
- JSON translation/manifest parsing: passed
- YAML syntax and duplicate-key scan: passed
- PowerShell installer parser: passed
- Bash is not installed in the audit environment, so `bash -n` was unavailable
- `git diff --check`: passed

The local environment does not include a full Home Assistant runtime, HA OS
CLI, or Home Assistant Docker container, so `hass --script check_config` and a
real config-entry startup test could not be run here. The repository mocks are
useful for deterministic analytics/unit tests but are not a substitute for that
final staging check.

## Known boundaries

- The customer portal APIs are private/undocumented and can change without a
  versioned contract. GraphQL failures remain isolated where partial data is
  optional, but authentication and core interval failures correctly make the
  entry unavailable or trigger reauthentication.
- Multiple active accounts are fetched correctly and balances are matched to the
  selected account, but first-time setup still selects the first active account
  rather than showing an account-picker step.
- Kaluza vehicle data depends on private, undocumented endpoints and may become
  temporarily unavailable independently of core energy data. It is treated as
  optional so an EV outage cannot take down account/usage sensors.
- Remote boost, charging-time mutation, charge-limit changes, unlink/remove,
  and other control actions are not shipped because no write was invoked during
  the audit and safe idempotency/confirmation contracts were not verified.
- Entity display-name translations and a full Home Assistant config-flow test
  harness remain quality-scale improvements, not data-correctness blockers;
  targeted options-flow behavior is covered by the local unit suite.

## Release target

The audited changes are versioned as **4.8.1** and are intended to be committed,
pushed, tagged, and published together with a verified forward-slash release
archive. The GitHub release is the deployment record; this report describes the
source and validation performed before that release was created.
