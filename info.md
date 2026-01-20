# OVO Energy Australia

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/HallyAus/OVO_Aus_api.svg)](https://github.com/HallyAus/OVO_Aus_api/releases)

Unofficial Home Assistant integration for OVO Energy Australia's GraphQL API.

## Features

- ☀️ **Solar Generation Tracking** - Monitor hourly and daily solar production
- ⚡ **Grid Export Monitoring** - Track energy exported to the grid
- 💰 **Cost Savings** - Calculate savings from solar generation
- 🔄 **Automatic Updates** - Data refreshes every 5 minutes
- 📊 **Energy Dashboard Compatible** - Works with HA Energy Dashboard

## Installation via HACS

### Prerequisites

- HACS installed in your Home Assistant instance
- OVO Energy Australia account with solar panels

### Add Custom Repository

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the 3 dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/HallyAus/OVO_Aus_api`
6. Select category: "Integration"
7. Click "Add"

### Install Integration

1. Search for "OVO Energy Australia" in HACS
2. Click "Download"
3. Restart Home Assistant

### Configuration

Add to your `configuration.yaml`:

```yaml
ovo_energy_au:
  access_token: "Bearer eyJ..."
  id_token: "eyJ..."
  account_id: "30264061"
```

Or use `secrets.yaml`:

```yaml
ovo_energy_au:
  access_token: !secret ovo_access_token
  id_token: !secret ovo_id_token
  account_id: !secret ovo_account_id
```

### Getting Your Tokens

1. Go to https://my.ovoenergy.com.au
2. Open DevTools (F12) → Network tab
3. Log in and click "Usage"
4. Filter by "graphql"
5. Click on any graphql request
6. Copy from Headers:
   - `authorization` → access_token (includes "Bearer ")
   - `myovo-id-token` → id_token
7. Copy from Payload:
   - `accountId` → account_id

**Note:** Tokens expire after 5 minutes. You'll need to update them periodically.

## Available Sensors

After configuration, you'll have these sensors:

- `sensor.ovo_energy_solar_generation_current_hour` - Solar this hour (kWh)
- `sensor.ovo_energy_grid_export_current_hour` - Export this hour (kWh)
- `sensor.ovo_energy_solar_generation_today` - Total solar today (kWh)
- `sensor.ovo_energy_grid_export_today` - Total export today (kWh)
- `sensor.ovo_energy_cost_savings_today` - Savings today (AUD)

## Known Limitations

- ⚠️ Tokens expire after 5 minutes (requires manual refresh)
- ⚠️ YAML configuration only (no UI config flow yet)
- ⚠️ Only tested with solar accounts

## Support

- 📖 [Full Documentation](https://github.com/HallyAus/OVO_Aus_api)
- 🐛 [Report Issues](https://github.com/HallyAus/OVO_Aus_api/issues)
- 💬 [Discussions](https://github.com/HallyAus/OVO_Aus_api/discussions)

## Python Client Available

This repository also includes a standalone Python client with OAuth 2.0 authentication. See the [main README](https://github.com/HallyAus/OVO_Aus_api) for details.

---

**Made with ☀️ for the Australian solar community**
