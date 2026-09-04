# OVO Energy Australia for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/badge/version-4.9.3-blue.svg)](https://github.com/HallyAus/OVO_Aus_api/releases)
[![CI](https://github.com/HallyAus/OVO_Aus_api/actions/workflows/ci.yml/badge.svg)](https://github.com/HallyAus/OVO_Aus_api/actions/workflows/ci.yml)

Track solar generation, grid consumption, costs, EV charging, and plan savings in Home Assistant.

## 💚 Support this project — it's my only income from it

Referrals below are the only thing funding ongoing development. Both you and I get credit.

### ⭐ [Star the repo on GitHub](https://github.com/HallyAus/OVO_Aus_api) — takes two seconds

### 🎁 OVO Energy — $180 credit
- **Referral code:** `daniel16485`
- **Direct OVO signup:** [https://www.ovoenergy.com.au/refer/daniel16485](https://www.ovoenergy.com.au/refer/daniel16485)
- **Friendly link:** [https://ovoreferralcode.com/](https://ovoreferralcode.com/)

- ✅ $180 credit (incl. GST) on all eligible plans — including The EV Plan (no EV required)
- ✅ Both you and the referrer get $180 — paid as $15/month over 12 months

### 🛰️ Starlink — 1 month free
👉 **[starlink.com/residential?referral=RC-2455784-77014-69](https://starlink.com/residential?referral=RC-2455784-77014-69&app_source=share)**

- ✅ One free month of Starlink service

## ✨ Features

- ☀️ **Comprehensive Sensors** — Solar, grid, export, charges, rate breakdowns, analytics
- 🧹 **Focused Entity Set** — Rotating Day 1-7/hourly-day entities are removed
- ⚡ **Tariff Period Indicator** — Free 3, Free 4, EV, paid super-off-peak and configured TOU periods with detected rates
- 🔌 **EV Charging Tracker** — Monthly and yearly EV charging kWh and cost
- 🚗 **Connected Vehicle** — Battery/range/cable/mode telemetry, charge limits,
  readiness and credential health, preferences, charge plans, charging-time
  configuration, and monthly EV energy/cost detail (read-only and privacy-filtered)
- 🧾 **Bill Estimator** — Projected monthly bill with standing charge included
- 🏆 **Plan Savings** — One entity with daily/monthly/yearly OVO savings, rating, and recommendation
- 💰 **Account Balance** — Current credit/balance on your OVO account
- 📈 **Energy Dashboard** — Compatible with HA's native Energy Dashboard
- 🔄 **Automatic Auth** — OAuth2 PKCE with auto-refresh, no manual tokens
- 🕓 **Honest Freshness** — Usage is marked non-real-time and stale dates are reported
- 🌏 **6 Languages** — English, Chinese, Vietnamese, Greek, Italian, Arabic
- 🤖 **Daily Report Blueprint** — Automated savings notification

## 🚀 Setup

1. Add custom repository in HACS: `https://github.com/HallyAus/OVO_Aus_api`
2. Download and restart Home Assistant
3. **Settings → Devices & Services → Add Integration → OVO Energy Australia**
4. Enter your OVO email and password — everything else is automatic

> ⚠️ **Important:** When adding the integration, select **OVO Energy Australia** (`ovo_energy_au`) — NOT Home Assistant's built-in **OVO Energy** integration, which is for OVO **UK**. If your error log mentions `homeassistant/components/ovo_energy` or `No customer id set`, you added the wrong one.

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
