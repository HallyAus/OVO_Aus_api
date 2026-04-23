# OVO Energy Australia for Home Assistant

<div align="center">

<img src="images/logo.svg" alt="OVO Energy Australia" width="280"/>

<br/><br/>

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?logo=homeassistantcommunitystore)](https://github.com/hacs/integration)
[![CI](https://github.com/HallyAus/OVO_Aus_api/actions/workflows/ci.yml/badge.svg)](https://github.com/HallyAus/OVO_Aus_api/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-4.1.0-blue.svg)](https://github.com/HallyAus/OVO_Aus_api/releases)
[![License: CC0-1.0](https://img.shields.io/badge/License-CC0%201.0-lightgrey.svg)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1+-green.svg?logo=homeassistant)](https://www.home-assistant.io/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)

![GitHub Stars](https://img.shields.io/github/stars/HallyAus/OVO_Aus_api?style=social)
![GitHub Forks](https://img.shields.io/github/forks/HallyAus/OVO_Aus_api?style=social)
![GitHub Issues](https://img.shields.io/github/issues/HallyAus/OVO_Aus_api)
![GitHub Last Commit](https://img.shields.io/github/last-commit/HallyAus/OVO_Aus_api)
![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support-orange.svg?logo=buy-me-a-coffee)](https://buymeacoffee.com/printforge)
![Powered by Coffee](https://img.shields.io/badge/Powered%20by-Coffee%20%E2%98%95-brown)
![Australian Made](https://img.shields.io/badge/Made%20in-Australia%20%F0%9F%87%A6%F0%9F%87%BA-green)
![Jedi Master](https://img.shields.io/badge/Energy%20Monitoring-Jedi%20Master%20Level-blue?logo=starwars)

**Comprehensive Home Assistant integration for OVO Energy Australia**

Track solar generation, grid consumption, costs, rate breakdowns, and OVO plan savings -- all from your Home Assistant dashboard.

> *"Use the Force wisely, young Padawan. Monitor your energy, you must."* -- Yoda (probably)

[Features](#features) · [Quick Start](#quick-start) · [Sensors](#sensors) · [Dashboards](#dashboard-examples) · [Contributing](#contributing)

</div>

---

## 💚 Support this project — it's my only income from it

If this integration saves you money or time, please use one of the referrals below. Both you and I get credit. This project is maintained in my spare time and referrals are the only thing funding ongoing development.

### ⭐ Star this repo
[**⭐ Star on GitHub**](https://github.com/HallyAus/OVO_Aus_api) — takes two seconds and genuinely helps. Stars surface the project to other OVO customers.

### 🎁 OVO Energy referral — $120–$180 credit
Not an OVO customer yet? Sign up using this referral link:

**👉 [www.ovoenergy.com.au/refer/daniel16485](https://www.ovoenergy.com.au/refer/daniel16485)**

- ✅ **$120 credit** paid over 12 months on standard plans
- ✅ **$180 credit** paid over 12 months if you choose The EV Plan
- ✅ Both you and I receive the credit — win-win

### 🛰️ Starlink referral — 1 month free
Running Home Assistant somewhere rural or need a reliable backup link?

**👉 [starlink.com/residential?referral=RC-2455784-77014-69](https://starlink.com/residential?referral=RC-2455784-77014-69&app_source=share)**

- ✅ One free month of Starlink service
- ✅ Works anywhere with a clear view of sky

---

## ✨ Features

### 📊 90+ Sensors with Automatic Plan Detection

The integration connects to OVO's GraphQL API and automatically detects your plan, rates, and account details. No manual rate entry required.

| Category | What You Get |
|----------|-------------|
| **Daily / Monthly / Yearly** | Solar generation, grid consumption, export -- both kWh and AUD |
| **Last 7 Days with Rate Breakdown** | Per-day split by rate type (EV_OFFPEAK, FREE_3, PEAK, SHOULDER, OFFPEAK, OTHER) |
| **OVO Savings** | Daily, monthly, and yearly savings vs the One Plan (calculated by OVO) |
| **Hourly Data** | 7-day rolling window with per-hour granularity and heatmap sensor |
| **Week-over-Week Comparison** | This week vs last week with percentage changes for solar, grid, and cost |
| **Weekday vs Weekend Analysis** | Average daily consumption and cost by day type |
| **Solar Self-Sufficiency** | Percentage of energy consumed from your own panels |
| **Monthly Cost Projection** | Budget forecast based on current daily average |
| **Cost per kWh** | Effective rates for grid, solar, and overall |
| **High Usage Day Rankings** | Top 5 consumption days from the last 30 days |
| **Hourly Heatmap** | Usage patterns by day-of-week and hour |
| **Solar Export Analysis** | Export credit, export rate, opportunity cost vs self-consumption |
| **Account Balance** | Current OVO account balance |
| **Plan Information** | Diagnostic sensor with all plan rates, standing charge, demand charge, NMI |
| **Integration Health** | Diagnostic sensor for monitoring API connectivity |
| **⚡ Tariff Period Indicator** | Shows current rate period (EV Off-Peak / FREE / Standard) with live rate |
| **📊 Plan Comparison** | Savings vs One Plan with rating and recommendation |
| **🔌 EV Charging Tracker** | Monthly and yearly EV charging kWh and cost |
| **🧾 Bill Estimator** | MTD bill, projected monthly bill, daily average net cost |

### 🏠 Real-World Results

One user on the **EV Plan** sees:

- **$1,066/year saved** vs the One Plan (OVO-calculated)
- **30--50 kWh/day** solar generation
- **8c/kWh** overnight EV charging (vs 37c standard rate)
- **Free electricity** 11 am -- 2 pm daily
- **2.8c/kWh** feed-in tariff

### ⚡ Technical Highlights

- **OAuth2 PKCE** authentication via Auth0 with automatic token refresh
- **401 retry** with automatic re-authentication
- **DST-aware** timezone handling using `ZoneInfo("Australia/Sydney")`
- **Dynamic hourly sensors** that survive midnight without a restart
- **Data-driven architecture** -- add sensors by editing a list, not writing classes
- **65 automated tests** with CI/CD via GitHub Actions
- **HACS compatible** with one-click install

---

## 🚀 Quick Start

### Install via HACS (Recommended)

Click the button below to add the repository in one step:

[![Open HACS Repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=HallyAus&repository=OVO_Aus_api&category=integration)

Or manually:

1. Open **HACS** > **Integrations** > three-dot menu > **Custom repositories**
2. Add `https://github.com/HallyAus/OVO_Aus_api` as an **Integration**
3. Click **Download**
4. Restart Home Assistant

### Manual Install

1. Download the [latest release](https://github.com/HallyAus/OVO_Aus_api/releases)
2. Copy `custom_components/ovo_energy_au` into your `config/custom_components/` directory
3. Restart Home Assistant

### Configure

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for **OVO Energy Australia**
3. Enter your OVO email and password
4. Done -- your plan, rates, and 90+ sensors are created automatically

> **Note:** OVO Energy **Australia** only. This integration does not work with OVO UK.

---

## 📡 Sensors

All sensors are grouped into logical device categories in Home Assistant for easy navigation.

### ⚡ Core Energy (Daily / Monthly / Yearly)

| Sensor | Unit | Description |
|--------|------|-------------|
| Solar Consumption | kWh | Energy consumed from solar panels |
| Grid Consumption | kWh | Energy drawn from the grid |
| Return to Grid | kWh | Energy exported to the grid |
| Solar Feed-in Credit | AUD | Credit earned from solar export |
| Grid Charge | AUD | Cost of grid energy |
| Return to Grid Charge | AUD | Value of exported energy |

These six sensors are available for each period: **Yesterday**, **This Month**, **This Year**, **Last Week**, **Last Month**, and **Month to Date**.

### 💰 Rate Breakdown (Last 7 Days)

Seven per-day sensors showing consumption and cost split by rate type:

| Rate Type | Example Use |
|-----------|-------------|
| `EV_OFFPEAK` | Overnight EV charging at discounted rate |
| `FREE_3` | Free electricity window (e.g., 11 am -- 2 pm) |
| `PEAK` | Highest-cost period |
| `SHOULDER` | Mid-cost period |
| `OFFPEAK` | Standard off-peak |
| `OTHER` | Catch-all for remaining intervals |

Each day also includes counterfactual analysis showing what you would have paid on a different rate structure.

### 🏆 OVO Savings

| Sensor | Description |
|--------|-------------|
| OVO Savings (Yesterday) | Daily savings vs the One Plan |
| OVO Savings (This Month) | Month-to-date savings |
| OVO Savings (This Year) | Year-to-date savings |

These values are calculated by OVO's own comparison engine, not estimated locally.

### 🧠 Analytics & Insights

| Sensor Group | Sensors | Purpose |
|-------------|---------|---------|
| Week Comparison | 6 | This week vs last week (solar, grid, cost + % change) |
| Weekday vs Weekend | 4 | Average daily consumption and cost by day type |
| Peak Usage | 1 | Highest consumption 4-hour window |
| Self-Sufficiency | 1 | Percentage of energy from solar |
| High Usage Days | 1 | Top 5 consumption days (last 30 days) |
| Hourly Heatmap | 1 | Day-of-week / hour usage grid |
| Cost per kWh | 3 | Effective rates (overall, grid, solar) |
| Monthly Forecast | 3 | Projected total, remaining, and daily average |
| Solar Export | 4 | Export credit, rate, potential savings, opportunity cost |

### ⏰ Hourly Data

- **7-day rolling window** with solar, grid, and export totals
- **Yesterday hourly** sensors for quick graph display
- Full hourly entries available in sensor attributes

### 🔧 Other

| Sensor | Category |
|--------|----------|
| Account Balance | Account |
| Plan Information | Diagnostic |
| Integration Health | Diagnostic |

---

## 📊 Dashboard Examples

Ready-to-use YAML dashboard configurations are included in [`docs/dashboards/`](docs/dashboards/):

| File | Description |
|------|-------------|
| `dashboard_simple.yaml` | Built-in cards only -- no custom components needed |
| `dashboard_example.yaml` | Comprehensive 4-view dashboard (mushroom + apexcharts) |
| `dashboard_hourly.yaml` | Dedicated hourly charts with solar/grid/export overlays |

Copy any of these into your Lovelace dashboard configuration to get started. They use standard Home Assistant cards and [ApexCharts Card](https://github.com/RomRider/apexcharts-card) for graphs.

### Quick Example

```yaml
type: entities
title: Yesterday's Energy
entities:
  - sensor.ovo_energy_au_daily_solar_consumption
  - sensor.ovo_energy_au_daily_grid_consumption
  - sensor.ovo_energy_au_daily_return_to_grid
  - sensor.ovo_energy_au_daily_grid_charge
  - sensor.ovo_energy_au_daily_ovo_savings
```

---

## 🏗️ Technical Details

### Architecture

```
custom_components/ovo_energy_au/
  __init__.py          # Integration setup (82 lines)
  coordinator.py       # DataUpdateCoordinator, 5-min polling
  api.py               # OAuth2 PKCE auth, GraphQL client
  sensor.py            # Sensor platform (~800 lines)
  config_flow.py       # UI config + options flow
  models.py            # TypedDict / dataclass definitions
  const.py             # Constants (~70 lines)
  graphql/
    queries.py         # All GraphQL query strings
  sensors/
    definitions.py     # Data-driven sensor definitions
    base.py            # Base sensor classes
  analytics/
    interval.py        # Daily/monthly/yearly aggregation
    hourly.py          # Hourly data processing
    insights.py        # Derived analytics (week comparison, heatmap, etc.)
```

### API

The integration communicates with OVO Energy Australia's GraphQL API:

- **Authentication:** OAuth2 PKCE flow via Auth0 (`auth.ovoenergy.com.au`)
- **Token refresh:** Automatic, with 401 retry and re-authentication fallback
- **Polling interval:** 5 minutes via Home Assistant's `DataUpdateCoordinator`
- **Data source:** Daily data is available after 6:00 AM for the previous day
- **Timezone:** `ZoneInfo("Australia/Sydney")` -- handles AEST/AEDT transitions correctly

### Null Safety

OVO's API can return `null` for charge fields when data is not yet available. All sensors handle this gracefully and show "Unknown" rather than crashing.

---

## 🔍 Troubleshooting

| Problem | Solution |
|---------|----------|
| OAuth authentication fails | Verify credentials are for OVO Energy **Australia** (not UK). Check HA logs for details. |
| Sensors show "Unknown" | Wait until after 6:00 AM for yesterday's data. Check the Integration Health diagnostic sensor. |
| Sensors missing after install | Restart Home Assistant. Check Developer Tools > States for `ovo_energy_au` entities. |
| Token expires frequently | The integration handles this automatically. If persistent, remove and re-add the integration. |

---

## 🤝 Contributing

Contributions are welcome. Here is how to get started:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-change`)
3. Run tests: `pytest tests/`
4. Run linting: `ruff check .`
5. Submit a pull request

### Areas Where Help Is Appreciated

- Dashboard templates and card examples
- Testing with different OVO plan types (Basic, One, Free 3)
- Documentation and guides
- Support for additional tariff structures

See [`CHANGELOG.md`](CHANGELOG.md) for version history and [`CLAUDE.md`](CLAUDE.md) for the project development guide.

---

## 💬 Support

- **Issues:** [GitHub Issues](https://github.com/HallyAus/OVO_Aus_api/issues)
- **Buy Me a Coffee:** [buymeacoffee.com/printforge](https://buymeacoffee.com/printforge)

---

## 📄 License

This project is released under the [CC0 1.0 Universal](LICENSE) license.

**Disclaimer:** This is an unofficial, community-built integration. It is not affiliated with, endorsed by, or supported by OVO Energy Australia.

---

<div align="center">

Built for the Australian solar and EV community.

</div>
