# Quick start

## Install with HACS

1. In HACS, add `https://github.com/HallyAus/OVO_Aus_api` as a custom
   **Integration** repository.
2. Install **OVO Energy Australia**.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**.
5. Search for **OVO Energy Australia** and enter your MyOVO email and password.

The integration completes OVO's Auth0 PKCE flow itself. Do not copy browser
tokens into YAML, screenshots, issues, or support messages.

## Configure the plan

Plan name and published rates are detected from MyOVO. To adjust billing-cycle
day or a plan-specific fallback rate, open the integration and choose
**Configure**. Saving options reloads the entry automatically.

## Energy Dashboard

Under **Settings → Dashboards → Energy**, select these entities as applicable:

- Grid import: `Grid Import (Energy Dashboard)`
- Return to grid: `Grid Export (Energy Dashboard)`
- Solar production: `Solar Production (Energy Dashboard)`

## Optional history entities

The integration offers detailed per-day and hourly-history entities. They are
disabled by default because enabling all of them creates substantial Recorder
and entity-registry load. Enable only the ones you use from the Entities page.

## Connected vehicles

Accounts enrolled in OVO EV Control automatically get a separate vehicle
device after the first refresh. It contains live telemetry, charging
preferences, schedule/charge-plan detail, and current-month vehicle energy and
cost. No additional configuration is required. The integration is read-only
and discards VIN, location/home state, raw IDs, tokens, and vendor certificate
URLs before creating Home Assistant entities.

## Troubleshooting

- `Invalid authentication`: verify the same credentials at MyOVO, then use the
  integration's **Reconfigure authentication** flow.
- No hourly data: OVO commonly publishes complete hourly data the following
  morning; the integration reports unavailable rather than inventing zeroes.
- Wrong billing period: set **Billing Cycle Start Day** in Configure.
- Manual refresh: run `ovo_energy_au.refresh_data` from Developer Tools → Actions.

Never attach Home Assistant `.storage` files, tokens, statement URLs, meter IDs,
or full diagnostics copied from unofficial tools to a public issue. The built-in
integration diagnostics are redacted for support use.
