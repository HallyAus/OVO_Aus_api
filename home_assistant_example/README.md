# OVO Energy Australia - Home Assistant Integration

This custom component integrates OVO Energy Australia with Home Assistant, providing real-time solar generation, grid export, and cost savings data.

## Features

- ☀️ **Solar Generation** - Current hour and daily totals
- ⚡ **Grid Export** - Current hour and daily totals
- 💰 **Cost Savings** - Daily savings from solar
- 🔄 **Automatic Updates** - Data refreshes every 5 minutes
- 📊 **Energy Dashboard** - Compatible with HA Energy Dashboard

## Installation

### Method 1: Manual Installation

1. **Copy files to Home Assistant:**
   ```bash
   cd /config  # or wherever your HA config directory is
   mkdir -p custom_components
   cp -r /path/to/OVO_Aus_api/home_assistant_example/custom_components/ovo_energy_au custom_components/
   ```

2. **Restart Home Assistant**

3. **Configure in `configuration.yaml`:**
   ```yaml
   ovo_energy_au:
     access_token: "Bearer eyJ..."  # Your JWT access token
     id_token: "eyJ..."              # Your JWT ID token
     account_id: "30264061"          # Your OVO account ID
   ```

4. **Restart Home Assistant again**

### Method 2: HACS (Future)

*Not yet available in HACS - manual installation only for now*

## Getting Your Tokens

**IMPORTANT:** Tokens expire every 5 minutes! This is a temporary limitation until OAuth is implemented.

### Step-by-Step Token Extraction

1. **Open Browser DevTools:**
   - Go to https://my.ovoenergy.com.au
   - Open DevTools (F12 or Right-click → Inspect)
   - Go to **Network** tab

2. **Log in to OVO:**
   - Log in with your credentials
   - Navigate to Usage page

3. **Find GraphQL Request:**
   - In Network tab, filter by "graphql"
   - Click on a `graphql` request
   - Go to **Headers** section

4. **Copy Tokens:**
   - Find `authorization` header - this is your `access_token` (includes "Bearer ")
   - Find `myovo-id-token` header - this is your `id_token`

5. **Find Account ID:**
   - In the same request, go to **Payload** section
   - Look for `accountId` in the variables
   - Copy the number (e.g., "30264061")

### Example Configuration

```yaml
ovo_energy_au:
  access_token: "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik..."
  id_token: "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik5qSTBOa..."
  account_id: "30264061"
```

## Available Sensors

After installation, you'll have these sensors:

| Sensor | Entity ID | Description |
|--------|-----------|-------------|
| Solar Generation (Current Hour) | `sensor.ovo_energy_solar_generation_current_hour` | Solar generated this hour (kWh) |
| Grid Export (Current Hour) | `sensor.ovo_energy_grid_export_current_hour` | Energy exported this hour (kWh) |
| Solar Generation (Today) | `sensor.ovo_energy_solar_generation_today` | Total solar generated today (kWh) |
| Grid Export (Today) | `sensor.ovo_energy_grid_export_today` | Total energy exported today (kWh) |
| Cost Savings (Today) | `sensor.ovo_energy_cost_savings_today` | Total savings today (AUD) |

## Using in Lovelace

### Energy Card Example

```yaml
type: energy-distribution
link_dashboard: true
```

### Custom Card Example

```yaml
type: entities
title: OVO Energy - Solar Today
entities:
  - entity: sensor.ovo_energy_solar_generation_today
    name: Solar Generated
  - entity: sensor.ovo_energy_grid_export_today
    name: Exported to Grid
  - entity: sensor.ovo_energy_cost_savings_today
    name: Cost Savings
```

### Gauge Card for Current Hour

```yaml
type: gauge
entity: sensor.ovo_energy_solar_generation_current_hour
min: 0
max: 5
name: Solar Power (Current Hour)
severity:
  green: 2
  yellow: 1
  red: 0
```

## Known Limitations

### 🔴 Critical Issues

1. **Token Expiry (5 minutes)**
   - Tokens expire after 5 minutes
   - You must manually update tokens in configuration.yaml
   - Sensors will stop updating after expiry
   - **Workaround:** Set up an automation to notify you when sensors go unavailable

2. **No OAuth Flow**
   - Must manually extract tokens from browser
   - Cannot authenticate with username/password
   - **Future:** OAuth implementation planned

3. **No Config Flow**
   - Configuration only via YAML
   - Cannot configure via UI
   - **Future:** Config flow planned

### ⚠️ Medium Priority Issues

1. **Blocking I/O**
   - Uses `requests` library (blocking)
   - Should use `aiohttp` for async
   - May cause slight delays in HA

2. **No Error Recovery**
   - When tokens expire, sensors become unavailable
   - Must manually restart HA after updating tokens

## Troubleshooting

### Sensors Show "Unavailable"

**Cause:** Tokens have expired (after 5 minutes)

**Solution:**
1. Extract fresh tokens from browser (see above)
2. Update `configuration.yaml` with new tokens
3. Restart Home Assistant

### "Authentication failed" Error in Logs

**Cause:** Invalid or missing tokens

**Solution:**
1. Check tokens are correctly copied (no extra spaces)
2. Ensure `access_token` includes "Bearer " prefix
3. Verify `account_id` is correct

### No Data Showing

**Cause:** May not have solar panels or data not available

**Solution:**
1. Check logs for errors: `config/home-assistant.log`
2. Verify your account has solar panels
3. Check you've navigated to Usage page in OVO web app recently

## Automation Example: Token Expiry Notification

Since tokens expire every 5 minutes, set up a notification:

```yaml
automation:
  - alias: "OVO Energy - Tokens Expired"
    trigger:
      - platform: state
        entity_id: sensor.ovo_energy_solar_generation_today
        to: "unavailable"
        for:
          minutes: 1
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "OVO Energy Tokens Expired"
          message: "Update tokens in configuration.yaml"
```

## Development Roadmap

### Planned Features

- [ ] OAuth 2.0 authentication (no manual tokens)
- [ ] Automatic token refresh
- [ ] Config flow (UI configuration)
- [ ] Async/await implementation
- [ ] Additional sensors (billing, account info)
- [ ] Historical data graphs
- [ ] HACS integration

## Support

- **GitHub Issues:** https://github.com/HallyAus/OVO_Aus_api/issues
- **Documentation:** See main README.md in repository root

## Credits

**Reverse-Engineered By:** Claude (Sonnet 4.5) + Daniel
**Date:** January 2026
**Status:** Prototype - Working but requires manual token management

## License

See LICENSE file in repository root.
