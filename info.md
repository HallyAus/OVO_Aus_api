# OVO Energy Australia for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/badge/version-4.1.1-blue.svg)](https://github.com/HallyAus/OVO_Aus_api/releases)
[![CI](https://github.com/HallyAus/OVO_Aus_api/actions/workflows/ci.yml/badge.svg)](https://github.com/HallyAus/OVO_Aus_api/actions/workflows/ci.yml)

Track solar generation, grid consumption, costs, EV charging, and plan savings in Home Assistant.

## 💚 Support this project — it's my only income from it

Referrals below are the only thing funding ongoing development. Both you and I get credit.

### ⭐ [Star the repo on GitHub](https://github.com/HallyAus/OVO_Aus_api) — takes two seconds

### 🎁 OVO Energy — $120-$180 credit
👉 **[www.ovoenergy.com.au/refer/daniel16485](https://www.ovoenergy.com.au/refer/daniel16485)**

- ✅ $120 credit on standard plans / $180 on The EV Plan
- ✅ Both you and the referrer get credit — paid over 12 months

### 🛰️ Starlink — 1 month free
👉 **[starlink.com/residential?referral=RC-2455784-77014-69](https://starlink.com/residential?referral=RC-2455784-77014-69&app_source=share)**

- ✅ One free month of Starlink service

## ✨ Features

- ☀️ **90+ Sensors** — Solar, grid, export, charges, rate breakdowns, analytics
- ⚡ **Tariff Period Indicator** — Live current rate period with cost per kWh
- 🔌 **EV Charging Tracker** — Monthly and yearly EV charging kWh and cost
- 🧾 **Bill Estimator** — Projected monthly bill with standing charge included
- 🏆 **OVO Savings** — Daily/monthly/yearly savings vs the One Plan (OVO-calculated)
- 📊 **Plan Comparison** — Rating and recommendation based on your actual savings
- 💰 **Account Balance** — Current credit/balance on your OVO account
- 📈 **Energy Dashboard** — Compatible with HA's native Energy Dashboard
- 🔄 **Automatic Auth** — OAuth2 PKCE with auto-refresh, no manual tokens
- 🌏 **6 Languages** — English, Chinese, Vietnamese, Greek, Italian, Arabic
- 🤖 **Daily Report Blueprint** — Automated savings notification

## 🚀 Setup

1. Add custom repository in HACS: `https://github.com/HallyAus/OVO_Aus_api`
2. Download and restart Home Assistant
3. **Settings → Devices & Services → Add Integration → OVO Energy Australia**
4. Enter your OVO email and password — everything else is automatic

> **Note:** OVO Energy **Australia** only. Not compatible with OVO UK.

## 📊 Dashboard Templates

Ready-to-use YAML dashboards included in [`docs/dashboards/`](https://github.com/HallyAus/OVO_Aus_api/tree/main/docs/dashboards):
- Simple (built-in cards only)
- Comprehensive (mushroom + apexcharts)
- Hourly data with solar/grid/export charts

## 💬 Support

- 📖 [Full Documentation](https://github.com/HallyAus/OVO_Aus_api)
- 🐛 [Report Issues](https://github.com/HallyAus/OVO_Aus_api/issues)
- ☕ [Buy Me a Coffee](https://buymeacoffee.com/printforge)

---

**Made with ☀️ for the Australian solar and EV community**
