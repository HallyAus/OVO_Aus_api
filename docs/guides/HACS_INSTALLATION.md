# HACS installation

## Recommended installation

1. Open **HACS → Integrations**.
2. Select the menu, then **Custom repositories**.
3. Add `https://github.com/HallyAus/OVO_Aus_api` with category **Integration**.
4. Search for and install **OVO Energy Australia**.
5. Restart Home Assistant.
6. Open **Settings → Devices & services → Add integration** and search for
   **OVO Energy Australia**.
7. Sign in with your MyOVO email and password.

No `configuration.yaml` block and no manually extracted JWT tokens are
supported or required.

## Manual installation

Download `ovo_energy_au.zip` from the latest GitHub release. Extract the
`ovo_energy_au` directory to:

```text
<config>/custom_components/ovo_energy_au/
```

Confirm that `manifest.json` is directly inside that directory, restart Home
Assistant, and add the integration through the UI.

The repository also includes `scripts/install.sh` and `scripts/install.ps1` for
interactive manual installation. Both install from the latest release/main
branch and finish with the same UI setup.

## Updates and removal

- Update from HACS, then restart Home Assistant.
- To remove the integration, delete its entry from **Devices & services**,
  uninstall it in HACS, and restart.

## Security

Home Assistant stores the credentials needed to reauthenticate with OVO in its
config-entry storage. Protect backups and the `.storage` directory. The client
uses Auth0 authorization-code + PKCE, validates OAuth state and ID-token nonce,
and prefers refresh-token rotation over repeatedly submitting the password.

Do not publish tokens, signed bill URLs, account numbers, NMIs, addresses, or
vehicle telemetry when requesting support. Use the built-in redacted diagnostics.
