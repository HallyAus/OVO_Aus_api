# OVO Energy Australia API Client

Unofficial Python client and Home Assistant integration for OVO Energy Australia's GraphQL API.

**Status:** ✅ Beta - OAuth authentication implemented with automatic token refresh

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/github/license/HallyAus/OVO_Aus_api)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Compatible-green.svg)](https://www.home-assistant.io/)

---

## Features

- ☀️ **Solar Generation Data** - Hourly solar production metrics
- ⚡ **Grid Export Tracking** - Monitor energy exported to the grid
- 💰 **Cost Savings** - Calculate savings from solar generation
- 🏠 **Home Assistant Integration** - Custom component with sensors
- 📊 **GraphQL API Client** - Full Python client with error handling
- 📝 **Comprehensive Documentation** - Complete API reference and guides

---

## Quick Start

### Home Assistant (HACS - Recommended) ⭐

```bash
# Install via HACS:
# 1. Add custom repository: https://github.com/HallyAus/OVO_Aus_api
# 2. Search for "OVO Energy Australia"
# 3. Click Download

# Or use auto-install script:
bash <(curl -s https://raw.githubusercontent.com/HallyAus/OVO_Aus_api/claude/create-github-project-rWeUP/install.sh)
```

For detailed instructions, see [HACS_INSTALLATION.md](HACS_INSTALLATION.md)

### Python Client

```bash
# Clone repository
git clone https://github.com/HallyAus/OVO_Aus_api.git
cd OVO_Aus_api

# Install dependencies
pip install -r requirements.txt

# Run example (supports OAuth!)
python3 ovo_australia_client.py
```

For detailed instructions, see [QUICK_START.md](QUICK_START.md)

---

## What This Project Provides

### 1. Python GraphQL Client

A complete Python client for interacting with OVO Energy Australia's API:

```python
from ovo_australia_client import OVOEnergyAU

# Create client
client = OVOEnergyAU(account_id="30264061")
client.set_tokens(access_token="Bearer ...", id_token="...")

# Get today's solar data
data = client.get_today_data()
print(f"Solar: {sum(p['consumption'] for p in data['solar'])} kWh")
```

**Features:**
- GraphQL query builder
- Automatic error handling
- Token management (basic)
- Convenience methods for common queries
- Context manager support

### 2. Home Assistant Custom Component

Pre-built custom component with 5 sensors:

- 🌞 Solar Generation (Current Hour)
- ⚡ Grid Export (Current Hour)
- 📊 Solar Generation (Today)
- 📈 Grid Export (Today)
- 💵 Cost Savings (Today)

### 3. Complete Documentation

- **[QUICK_START.md](QUICK_START.md)** - Get started in 5 minutes
- **[OVO_AU_API_DOCUMENTATION.md](OVO_AU_API_DOCUMENTATION.md)** - Complete API reference
- **[BROWSER_TESTING_GUIDE.md](BROWSER_TESTING_GUIDE.md)** - How we discovered the API
- **[ovo_australia_conversion_guide.md](ovo_australia_conversion_guide.md)** - Migrate from OVO UK

---

## Project Status

### ✅ What Works

- ✅ **OAuth 2.0 Authentication** - Full username/password login with PKCE
- ✅ **Automatic Token Refresh** - Tokens refresh automatically every 4 minutes
- ✅ GraphQL API client with authentication
- ✅ Hourly energy data retrieval
- ✅ Solar generation tracking
- ✅ Grid export tracking
- ✅ Cost savings calculation
- ✅ Home Assistant custom component
- ✅ Error handling and logging
- ✅ Comprehensive documentation

### 🚧 Known Limitations

- ⚠️ **OAuth Success Rate** - May not work for all Auth0 configurations (fallback to manual tokens available)
- ⚠️ **Account ID** - May need to be entered manually after OAuth login
- ⚠️ **Home Assistant YAML Configuration Only** - No UI config flow (can use manual tokens)
- ⚠️ **Blocking I/O in HA Component** - Should be async
- ⚠️ **Only Tested with Solar Accounts** - Non-solar accounts untested

### 🎯 Roadmap

**Recently Completed:** ✅
- [x] Implement OAuth 2.0 authentication flow with PKCE
- [x] Automatic token refresh mechanism

**High Priority:**
- [ ] Improve OAuth compatibility (test with more account types)
- [ ] Auto-detect account ID after OAuth login
- [ ] Home Assistant config flow (UI setup)
- [ ] Async/await implementation for HA

**Medium Priority:**
- [ ] Additional GraphQL queries (billing, account details)
- [ ] Daily/monthly data aggregation
- [ ] Rate limiting and request throttling
- [ ] Comprehensive error recovery
- [ ] Unit tests for OAuth flow

**Low Priority:**
- [ ] HACS integration
- [ ] Documentation improvements
- [ ] Support for non-solar accounts

---

## Installation

### Home Assistant Installation

**Choose one method:**

#### Option 1: HACS (Recommended) ⭐

Most users should use HACS for easy installation and updates:

📖 **[Complete HACS Installation Guide →](HACS_INSTALLATION.md)**

Quick steps:
1. Add custom repository: `https://github.com/HallyAus/OVO_Aus_api`
2. Search "OVO Energy Australia" in HACS
3. Download and configure

#### Option 2: Auto Install Script

One-command installation:

**Linux/macOS/Docker:**
```bash
bash <(curl -s https://raw.githubusercontent.com/HallyAus/OVO_Aus_api/claude/create-github-project-rWeUP/install.sh)
```

**Windows PowerShell:**
```powershell
iwr https://raw.githubusercontent.com/HallyAus/OVO_Aus_api/claude/create-github-project-rWeUP/install.ps1 -UseBasicParsing | iex
```

#### Option 3: Manual Installation

See [HACS_INSTALLATION.md](HACS_INSTALLATION.md#method-3-manual-installation) for manual steps.

### Python Client Installation

**Requirements:**
- Python 3.11+
- OVO Energy Australia account

**Install:**

```bash
# Clone repository
git clone https://github.com/HallyAus/OVO_Aus_api.git
cd OVO_Aus_api

# Install dependencies
pip install -r requirements.txt

# Run with OAuth authentication
python3 ovo_australia_client.py
```

---

## Usage Examples

### Basic Usage with OAuth

```python
from ovo_australia_client import OVOEnergyAU

# Initialize client
client = OVOEnergyAU()

# Authenticate with username and password
client.authenticate("your.email@example.com", "your_password")

# Set account ID (if not auto-detected)
client.account_id = "30264061"

# Get today's data
data = client.get_today_data()

# Calculate totals
total_solar = sum(p['consumption'] for p in data['solar'])
total_export = sum(p['consumption'] for p in data['export'])

print(f"Solar generated: {total_solar:.2f} kWh")
print(f"Exported to grid: {total_export:.2f} kWh")

# Token refresh happens automatically!
# Clean up
client.close()
```

### Basic Usage with Manual Tokens (Fallback)

```python
from ovo_australia_client import OVOEnergyAU

# Initialize client
client = OVOEnergyAU(account_id="30264061")
client.set_tokens(
    access_token="Bearer eyJ...",
    id_token="eyJ..."
)

# Get today's data
data = client.get_today_data()

# Clean up
client.close()
```

### Context Manager

```python
from ovo_australia_client import OVOEnergyAU

with OVOEnergyAU(account_id="30264061") as client:
    client.set_tokens(access_token="Bearer ...", id_token="...")

    # Get last 7 days
    data = client.get_last_7_days()

    # Process data
    for point in data['solar']:
        print(f"{point['periodFrom']}: {point['consumption']} kWh")
```

### Error Handling

```python
from ovo_australia_client import (
    OVOEnergyAU,
    OVOAuthenticationError,
    OVOAPIError,
    OVOTokenExpiredError
)

try:
    client = OVOEnergyAU(account_id="30264061")
    client.set_tokens(access_token="...", id_token="...")
    data = client.get_today_data()

except OVOTokenExpiredError:
    print("Tokens expired - get fresh tokens from browser")

except OVOAPIError as e:
    print(f"API error: {e}")

finally:
    client.close()
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [QUICK_START.md](QUICK_START.md) | Get started in 5 minutes |
| [OVO_AU_API_DOCUMENTATION.md](OVO_AU_API_DOCUMENTATION.md) | Complete API reference |
| [BROWSER_TESTING_GUIDE.md](BROWSER_TESTING_GUIDE.md) | How to extract tokens and discover API endpoints |
| [ovo_australia_conversion_guide.md](ovo_australia_conversion_guide.md) | Migrate from OVO UK to OVO Australia |
| [home_assistant_example/README.md](home_assistant_example/README.md) | Home Assistant integration guide |

---

## API Overview

### Authentication

OVO Australia uses **Auth0 OAuth 2.0** with dual JWT tokens:

| Token | Header | Lifespan |
|-------|--------|----------|
| Access Token | `authorization` | 5 minutes |
| ID Token | `myovo-id-token` | 5 minutes |

**Current Limitation:** Tokens must be manually extracted from browser. See [QUICK_START.md](QUICK_START.md) for instructions.

### Endpoints

**GraphQL API:**
```
POST https://my.ovoenergy.com.au/graphql
```

**Auth0:**
```
https://login.ovoenergy.com.au
```

### Available Queries

| Query | Status | Description |
|-------|--------|-------------|
| `GetHourlyData` | ✅ Documented | Hourly energy data (solar/export/savings) |
| `getAccountDetails` | ⚠️ Discovered | Account information (not documented) |
| `getBillingHistory` | ⚠️ Discovered | Billing statements (not documented) |
| `getDailyData` | ⚠️ Discovered | Daily aggregated data (not documented) |

---

## Home Assistant Integration

### Features

- 🔄 Automatic data updates every 5 minutes
- 📊 5 sensors for solar and export tracking
- ⚡ Energy dashboard compatible
- 📈 Historical data support
- 🎨 Customizable Lovelace cards

### Sensors

| Sensor | Entity ID | Unit |
|--------|-----------|------|
| Solar Generation (Current) | `sensor.ovo_energy_solar_generation_current_hour` | kWh |
| Grid Export (Current) | `sensor.ovo_energy_grid_export_current_hour` | kWh |
| Solar Generation (Today) | `sensor.ovo_energy_solar_generation_today` | kWh |
| Grid Export (Today) | `sensor.ovo_energy_grid_export_today` | kWh |
| Cost Savings (Today) | `sensor.ovo_energy_cost_savings_today` | AUD |

### Example Dashboard

```yaml
type: entities
title: OVO Energy - Solar Today
entities:
  - entity: sensor.ovo_energy_solar_generation_today
  - entity: sensor.ovo_energy_grid_export_today
  - entity: sensor.ovo_energy_cost_savings_today
```

See [home_assistant_example/README.md](home_assistant_example/README.md) for more examples.

---

## Contributing

Contributions are welcome! This project needs help with:

1. **OAuth Implementation** (High Priority)
   - Implement Auth0 PKCE flow
   - Automatic token refresh
   - See handover document for details

2. **API Discovery**
   - Document additional GraphQL queries
   - Test with non-solar accounts
   - Find rate limits

3. **Home Assistant**
   - Implement config flow
   - Convert to async/await
   - Add more sensors

4. **Testing**
   - Write unit tests
   - Integration tests
   - Test edge cases

### How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test thoroughly
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

---

## Troubleshooting

### OAuth Authentication Fails

**Problem:** `authenticate()` method fails

**Solutions:**
1. Verify your email and password are correct
2. Check if your account uses MFA/2FA (not yet supported)
3. Fall back to manual token extraction
4. Check logs with `logging.basicConfig(level=logging.DEBUG)`

### Tokens Expire After Login

**Problem:** Tokens expire and aren't refreshing

**Solutions:**
- This shouldn't happen anymore with OAuth! Token refresh is automatic
- If using manual tokens, you need to provide a `refresh_token`
- Check logs to see if refresh is failing

### "Authentication failed" Error

**Problem:** Invalid or missing tokens

**Solutions:**
1. Verify tokens are copied correctly (no extra spaces)
2. Ensure `access_token` includes "Bearer " prefix
3. Check `id_token` doesn't include "Bearer "
4. Get fresh tokens if older than 5 minutes

### No Data Showing

**Problem:** Empty arrays returned

**Possible Causes:**
1. Wrong account ID
2. No solar panels on account
3. Data not yet available for today

**Solutions:**
1. Verify account ID from browser
2. Try yesterday's data instead
3. Check OVO web app shows data

See [QUICK_START.md](QUICK_START.md) for more troubleshooting.

---

## Security

### Token Security

⚠️ **Never commit tokens to git!**

Tokens are sensitive credentials:
- Can access your account data
- Could be used to view billing information
- Expire after 5 minutes (limited risk)

**Best Practices:**
```bash
# Add to .gitignore
*.env
tokens.txt
config.yaml
```

### Reporting Security Issues

Please report security issues privately to the maintainers.

---

## FAQ

**Q: Is this official?**
A: No. This is an unofficial, reverse-engineered client. Not endorsed by OVO Energy.

**Q: Will it break?**
A: Possibly. OVO can change their API anytime without notice.

**Q: Do I need solar panels?**
A: Recommended but not required. The client is optimized for solar accounts.

**Q: Why can't I just use username/password?**
A: OAuth flow not yet implemented. Contributions welcome!

**Q: Can I use this commercially?**
A: Check OVO's Terms of Service. This is for personal use.

**Q: Does this work with OVO UK?**
A: No. OVO UK uses a different API. See [ovo_australia_conversion_guide.md](ovo_australia_conversion_guide.md)

---

## Credits

**Reverse-Engineered By:** Claude (Sonnet 4.5) + Daniel
**Date:** January 2026
**Method:** Browser DevTools network analysis
**Status:** Prototype with working API calls

### Acknowledgments

- OVO Energy Australia for providing excellent solar tracking
- Home Assistant community for integration patterns
- Auth0 for OAuth documentation

---

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

**Disclaimer:** This is an unofficial project. Not affiliated with, endorsed by, or supported by OVO Energy Australia.

---

## Links

- **GitHub Repository:** https://github.com/HallyAus/OVO_Aus_api
- **Issues:** https://github.com/HallyAus/OVO_Aus_api/issues
- **OVO Energy Australia:** https://www.ovoenergy.com.au
- **Home Assistant:** https://www.home-assistant.io

---

## Support

- 📖 **Documentation:** See docs in this repository
- 🐛 **Bug Reports:** Open an issue on GitHub
- 💡 **Feature Requests:** Open an issue with enhancement tag
- ❓ **Questions:** Open a discussion on GitHub

---

## Changelog

### [0.2.0] - 2026-01-20

**OAuth Authentication Release**
- ✅ **NEW:** OAuth 2.0 authentication with PKCE flow
- ✅ **NEW:** Automatic token refresh every 4 minutes
- ✅ **NEW:** Multiple authentication strategies (ROPC, password realm, database connection)
- ✅ **NEW:** Account ID extraction from JWT tokens
- ✅ Improved error handling and logging
- ✅ Updated documentation and examples
- ✅ Fallback to manual tokens if OAuth fails

### [0.1.0] - 2026-01-20

**Initial Release**
- ✅ GraphQL API client
- ✅ Basic authentication (manual tokens)
- ✅ GetHourlyData query implementation
- ✅ Home Assistant custom component
- ✅ Complete documentation

---

**Made with ☀️ for the Australian solar community**
