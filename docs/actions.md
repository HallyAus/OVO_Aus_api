# Actions

## `ovo_energy_au.refresh_data`

Requests an immediate refresh for every loaded OVO Energy Australia config
entry. The action has no fields.

Use this for troubleshooting or after OVO publishes delayed usage data. Routine
automations should rely on the integration's normal polling interval instead of
calling the action frequently.

```yaml
action: ovo_energy_au.refresh_data
```
