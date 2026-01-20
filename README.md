# OVO Energy Australia - Home Assistant Integration

<div align="center">

[![Version](https://img.shields.io/badge/version-2.4.0-blue.svg)](https://github.com/HallyAus/OVO_Aus_api/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Compatible-green.svg)](https://www.home-assistant.io/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/github/license/HallyAus/OVO_Aus_api)](LICENSE)

**Comprehensive Home Assistant integration for OVO Energy Australia**
Track solar generation, grid consumption, costs, and get powerful analytics to optimize your energy usage.

[Features](#-features) • [Installation](#-installation) • [Sensors](#-sensors) • [Analytics](#-advanced-analytics) • [Support](#-support)

</div>

---

## ✨ Features

### 📊 **80+ Sensors** - Complete Energy Monitoring
- **Yesterday's Data** - Daily consumption and cost (updated at 6am)
- **This Month** - Current billing period totals
- **This Year** - Year-to-date tracking
- **Hourly Data** - Last 7 days breakdown
- **Last Week** - 7-day rolling totals
- **Last Month** - Previous month complete data
- **Month to Date** - Current calendar month
- **3 Day Snapshot** - Last 3 days with dynamic day names and dates

### 🧠 **10 Advanced Analytics Features** (New in v2.4.0)
1. **Peak Usage Time Blocks** - Find your highest consumption 4-hour window
2. **Week-over-Week Comparison** - Track weekly trends with % changes
3. **Weekday vs Weekend Analysis** - Compare usage patterns
4. **Time-of-Use Breakdown** - Peak/Shoulder/Off-Peak period tracking
5. **Solar Self-Sufficiency Score** - % of energy from solar
6. **High Usage Day Rankings** - Top 5 consumption days
7. **Hourly Heatmap Data** - Visual usage patterns by day/hour
8. **Cost Per kWh Tracking** - Effective rates for grid, solar, overall
9. **Monthly Cost Projection** - Budget forecasting
10. **Return-to-Grid Value Analysis** - Solar export ROI tracking

### 🎨 **Organized Device Categories**
All sensors grouped logically in Home Assistant:
- Yesterday, This Month, This Year
- Hourly Data, Last Week, Last Month, Month to Date
- 3 Day Snapshot
- Peak Usage, Week Comparison, Weekday vs Weekend
- Time of Use, Solar Insights, Usage Rankings
- Usage Patterns, Cost Analysis, Monthly Forecast, Solar Export

### 🔄 **Automatic Updates**
- OAuth 2.0 authentication with automatic token refresh
- Data updates every 5 minutes
- No manual intervention required
- Seamless integration with Home Assistant

---

## 🚀 Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the 3 dots in the top right corner
4. Select "Custom repositories"
5. Add repository URL: `https://github.com/HallyAus/OVO_Aus_api`
6. Select category: "Integration"
7. Click "Download"
8. Restart Home Assistant
9. Go to Settings → Devices & Services → Add Integration
10. Search for "OVO Energy Australia"
11. Follow the setup wizard

### Manual Installation

1. Download the latest release
2. Copy `custom_components/ovo_energy_au` to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant
4. Go to Settings → Devices & Services → Add Integration
5. Search for "OVO Energy Australia"

---

## 📈 Sensors

### Core Energy Tracking (Yesterday - Available at 6am)

| Sensor | Description | Unit |
|--------|-------------|------|
| Solar Consumption | Energy from solar panels | kWh |
| Grid Consumption | Energy from grid | kWh |
| Return to Grid | Energy exported | kWh |
| Solar Charge | Cost of solar energy | AUD |
| Grid Charge | Cost of grid energy | AUD |
| Return to Grid Charge | Credit from exports | AUD |

### Historical Periods

**This Month** - Current billing period totals
**This Year** - Year-to-date consumption and costs
**Last Week** - 7-day rolling totals with all metrics
**Last Month** - Previous month complete breakdown
**Month to Date** - Current calendar month progress

**3 Day Snapshot** - Last 3 days with dynamic names:
- Each day labeled with actual day name and date (e.g., "Monday 20 Jan")
- 4 sensors per day (solar consumption, solar charge, grid consumption, grid charge)
- Automatically updates with new data

### Hourly Data

- Solar Consumption (Last 7 Days)
- Grid Consumption (Last 7 Days)
- Return to Grid (Last 7 Days)
- Full hourly breakdown in sensor attributes

---

## 🧠 Advanced Analytics

### 1. Peak Usage Time Blocks

Identifies your highest consumption 4-hour window.

**Sensors:**
- `sensor.ovo_energy_au_peak_4hour_consumption` - Total consumption in peak window

**Attributes:**
- Start time and end time
- Hourly breakdown of the peak period
- Consumption by type (solar/grid)

**Use Case:** Identify when to reduce usage or shift heavy appliances to off-peak times.

---

### 2. Week-over-Week Comparison

Compare current week vs previous week to track trends.

**Sensors:**
- `sensor.ovo_energy_au_week_comparison_solar` - This week's solar consumption
- `sensor.ovo_energy_au_week_comparison_grid` - This week's grid consumption
- `sensor.ovo_energy_au_week_comparison_cost` - This week's total cost
- `sensor.ovo_energy_au_week_comparison_solar_change_pct` - Solar % change
- `sensor.ovo_energy_au_week_comparison_grid_change_pct` - Grid % change
- `sensor.ovo_energy_au_week_comparison_cost_change_pct` - Cost % change

**Attributes:**
- Last week's values
- Absolute change
- Percentage change
- Complete metrics for both weeks

**Use Case:** Track if behavior changes are reducing your bills.

---

### 3. Weekday vs Weekend Analysis

Understand different usage patterns between work and home days.

**Sensors:**
- `sensor.ovo_energy_au_weekday_avg_consumption` - Average weekday consumption
- `sensor.ovo_energy_au_weekend_avg_consumption` - Average weekend consumption
- `sensor.ovo_energy_au_weekday_avg_cost` - Average weekday cost
- `sensor.ovo_energy_au_weekend_avg_cost` - Average weekend cost

**Attributes:**
- Solar and grid breakdown
- Number of days included
- Average consumption per day type

**Use Case:** Identify differences in work-from-home vs weekend energy patterns.

---

### 4. Time-of-Use Cost Breakdown

Split usage into peak/shoulder/off-peak periods (Australian TOU tariffs).

**Time Periods:**
- **Peak:** 2pm-8pm weekdays (highest rates)
- **Shoulder:** 7am-2pm and 8pm-10pm weekdays, 7am-10pm weekends
- **Off-Peak:** 10pm-7am all days (lowest rates)

**Sensors:**
- `sensor.ovo_energy_au_tou_peak_consumption` - Peak period usage
- `sensor.ovo_energy_au_tou_shoulder_consumption` - Shoulder period usage
- `sensor.ovo_energy_au_tou_off_peak_consumption` - Off-peak period usage

**Attributes:**
- Consumption and cost per period
- Hours in each period

**Use Case:** Optimize usage timing to reduce bills by shifting consumption to off-peak.

---

### 5. Solar Self-Sufficiency Score

Measure how well your solar panels meet your energy needs.

**Sensor:**
- `sensor.ovo_energy_au_self_sufficiency_score` - Percentage (0-100%)

**Calculation:** `(Solar Consumption / Total Consumption) × 100`

**Attributes:**
- Solar kWh consumed
- Grid kWh consumed
- Total consumption
- Period days

**Use Case:** Track solar independence and identify opportunities to increase self-sufficiency.

---

### 6. High Usage Day Rankings

Identify your top consumption days to understand usage spikes.

**Sensor:**
- `sensor.ovo_energy_au_high_usage_days` - Highest consumption day value

**Attributes:**
- Top 5 highest consumption days (last 30 days)
- Date, day name, total consumption, total cost
- Solar and grid breakdown for each day

**Use Case:** Spot unusual usage patterns and correlate with activities or weather.

---

### 7. Hourly Heatmap Data

Visual representation of usage patterns by day of week and hour.

**Sensor:**
- `sensor.ovo_energy_au_hourly_heatmap` - Number of days available

**Attributes:**
- Complete heatmap data structure
- Average consumption for each day/hour combination
- Day names with hourly averages

**Use Case:** Create visual heatmap dashboards showing weekly energy patterns.

---

### 8. Cost Per kWh Tracking

Understand your effective energy rates.

**Sensors:**
- `sensor.ovo_energy_au_cost_per_kwh_overall` - Overall effective rate
- `sensor.ovo_energy_au_cost_per_kwh_grid` - Grid purchase rate
- `sensor.ovo_energy_au_cost_per_kwh_solar` - Solar consumption rate

**Calculation:** `Total Cost / Total Consumption` (based on last 7 days)

**Attributes:**
- All three rates
- Total cost and consumption

**Use Case:** Validate billing and understand true energy costs.

---

### 9. Monthly Cost Projection

Budget forecasting based on current usage patterns.

**Sensors:**
- `sensor.ovo_energy_au_monthly_projection_total` - Projected month-end cost
- `sensor.ovo_energy_au_monthly_projection_remaining` - Projected remaining cost
- `sensor.ovo_energy_au_monthly_daily_average` - Daily average cost

**Attributes:**
- Current month-to-date cost
- Days elapsed and remaining
- Daily average used for projection

**Use Case:** Stay on budget throughout the month with early warnings.

---

### 10. Return-to-Grid Value Analysis

Understand your solar export economics and ROI.

**Sensors:**
- `sensor.ovo_energy_au_rtg_export_credit` - Credit earned from exports
- `sensor.ovo_energy_au_rtg_export_rate` - Export rate per kWh
- `sensor.ovo_energy_au_rtg_potential_savings` - What you'd pay if you bought this power
- `sensor.ovo_energy_au_rtg_opportunity_cost` - Difference between purchase and export rates

**Attributes:**
- Export kWh
- Export credit earned
- Purchase rate per kWh
- Rate difference
- Complete value analysis

**Use Case:** Maximize solar ROI by understanding export value vs self-consumption.

---

## 🎨 Dashboard Examples

### Energy Overview Card

```yaml
type: vertical-stack
cards:
  - type: sensor
    entity: sensor.ovo_energy_au_self_sufficiency_score
    name: Solar Self-Sufficiency
    graph: line

  - type: entities
    title: Yesterday's Energy
    entities:
      - sensor.ovo_energy_au_daily_solar_consumption
      - sensor.ovo_energy_au_daily_grid_consumption
      - sensor.ovo_energy_au_daily_return_to_grid

  - type: entities
    title: Yesterday's Costs
    entities:
      - sensor.ovo_energy_au_daily_solar_charge
      - sensor.ovo_energy_au_daily_grid_charge
      - sensor.ovo_energy_au_daily_return_to_grid_charge
```

### Week Comparison Card

```yaml
type: entities
title: Week over Week
entities:
  - entity: sensor.ovo_energy_au_week_comparison_solar_change_pct
    name: Solar Change
  - entity: sensor.ovo_energy_au_week_comparison_grid_change_pct
    name: Grid Change
  - entity: sensor.ovo_energy_au_week_comparison_cost_change_pct
    name: Cost Change
```

### Budget Forecast Card

```yaml
type: entities
title: Monthly Forecast
entities:
  - sensor.ovo_energy_au_monthly_projection_total
  - sensor.ovo_energy_au_monthly_projection_remaining
  - sensor.ovo_energy_au_monthly_daily_average
```

### Time of Use Card

```yaml
type: horizontal-stack
cards:
  - type: sensor
    entity: sensor.ovo_energy_au_tou_peak_consumption
    name: Peak

  - type: sensor
    entity: sensor.ovo_energy_au_tou_shoulder_consumption
    name: Shoulder

  - type: sensor
    entity: sensor.ovo_energy_au_tou_off_peak_consumption
    name: Off-Peak
```

---

## 🔧 Configuration

### OAuth Authentication Setup

The integration uses OAuth 2.0 for secure authentication:

1. Add the integration via Settings → Devices & Services
2. Enter your OVO Energy Australia email and password
3. The integration automatically:
   - Authenticates via OAuth
   - Extracts tokens
   - Sets up automatic token refresh
   - Fetches your account ID

### Manual Configuration (Advanced)

If OAuth fails, you can manually provide tokens:

1. Log in to https://my.ovoenergy.com.au
2. Open browser DevTools (F12) → Network tab
3. Refresh the page
4. Find a GraphQL request
5. Copy the authorization tokens
6. Enter them in the integration setup

---

## 📊 Data Update Intervals

- **API Polling:** Every 5 minutes
- **Token Refresh:** Automatic when needed
- **Yesterday's Data:** Available at 6:00 AM daily
- **Hourly Data:** Last 7 days rolling window
- **Historical Data:** Updated with each refresh

---

## ❓ FAQ

**Q: How many sensors does this create?**
A: 80+ sensors organized into 17 device categories for easy navigation.

**Q: Will this work without solar panels?**
A: Yes! Grid consumption tracking works for all accounts. Solar sensors will show zero if you don't have panels.

**Q: Why does "Yesterday" data appear instead of "Today"?**
A: OVO's API provides daily data at 6am for the PREVIOUS day. This is accurately labeled as "Yesterday" to avoid confusion.

**Q: Do I need to update tokens manually?**
A: No! OAuth tokens refresh automatically. No manual intervention needed.

**Q: Can I see hourly data?**
A: Yes! Hourly sensors include the last 7 days of data in their attributes, plus the heatmap provides hourly breakdowns by day of week.

**Q: What's the difference between "This Month" and "Month to Date"?**
A: "This Month" is your billing period (varies by account). "Month to Date" is the current calendar month.

**Q: How accurate are the projections?**
A: Monthly projections are based on your current daily average. Accuracy improves as the month progresses.

**Q: Can I track multiple OVO accounts?**
A: Yes! Add the integration multiple times with different credentials.

---

## 🐛 Troubleshooting

### Authentication Fails

**Problem:** OAuth authentication doesn't work

**Solutions:**
1. Verify email and password are correct
2. Try the manual token method
3. Check Home Assistant logs for error details
4. Ensure you're using OVO Energy Australia (not UK)

### No Data Showing

**Problem:** Sensors show "Unknown" or zero values

**Solutions:**
1. Wait until 6am for yesterday's data to appear
2. Check that your account has active services
3. Verify in the OVO web app that data is available
4. Check Home Assistant logs for API errors

### Sensors Not Appearing

**Problem:** Integration loads but sensors missing

**Solutions:**
1. Restart Home Assistant after installation
2. Check Developer Tools → States to see all entities
3. Clear browser cache
4. Check if entities are disabled (Settings → Devices & Services → OVO Energy AU)

---

## 🔐 Security & Privacy

- All authentication uses OAuth 2.0 with automatic token refresh
- Tokens are stored securely in Home Assistant's config entries
- No data is sent to third parties
- All communication is directly between Home Assistant and OVO's API
- Tokens expire and refresh automatically for security

**Never share your tokens or credentials publicly!**

---

## 📝 Changelog

### [2.4.0] - 2026-01-20

**Major Analytics Release** 🎉

**Added:**
- ✨ 10 comprehensive energy analytics features
- 📊 32 new sensors for advanced insights
- 🧠 Peak usage time block identification
- 📈 Week-over-week comparison tracking
- 📅 Weekday vs weekend analysis
- ⏰ Time-of-use cost breakdown
- ☀️ Solar self-sufficiency score
- 🏆 High usage day rankings
- 🗺️ Hourly heatmap data
- 💰 Cost per kWh tracking
- 🔮 Monthly cost projection
- 💸 Return-to-grid value analysis
- 🎨 10 new device categories for organization
- 📋 Comprehensive sensor attributes for dashboards

**Total Sensors:** 80+ (48 existing + 32 new)

### [2.3.0] - 2026-01-20

**Sensor Organization Release**

**Added:**
- 🎯 Device categories for logical sensor grouping
- 📁 8 main device groups (Yesterday, This Month, etc.)
- 🎨 Cleaner sensor names
- ✨ Better Home Assistant UI organization

### [2.2.0] - 2026-01-20

**Historical Period Sensors Release**

**Added:**
- 📅 Last 7 Days sensors (4 total)
- 📆 Last Month sensors (4 total)
- 📊 Month to Date sensors (4 total)
- 🗓️ Dynamic 3-day sensors with actual day names and dates
- 🎯 12 sensors for last 3 days (4 per day)
- ✨ Automatic day name updates (e.g., "Monday 20 Jan")

### [2.1.0] - 2026-01-20

**Monthly Breakdown Release**

**Added:**
- 📊 Monthly charge graphs with daily breakdown
- 📈 Daily statistics (average, max)
- 🎨 Dashboard examples with ApexCharts
- 📋 Complete daily breakdown attributes

### [2.0.0] - 2026-01-20

**Config Flow & Auto-Refresh Release**

**Added:**
- ✅ Home Assistant UI configuration flow
- 🔄 Automatic token refresh
- 🎯 OAuth 2.0 authentication
- ✨ No more YAML configuration needed

---

## 💖 Support This Project

If you find this integration useful, consider supporting its development!

<a href="https://buymeacoffee.com/printforge" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" >
</a>

Your support helps:
- 🚀 Develop new features
- 🐛 Fix bugs faster
- 📚 Improve documentation
- ⚡ Keep the integration updated with OVO API changes

**Other ways to support:**
- ⭐ Star this repository on GitHub
- 🐛 Report bugs and suggest features
- 📝 Improve documentation
- 💬 Share with other OVO Energy users

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Development

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

### Areas That Need Help

- 🔧 Additional analytics features
- 🎨 Dashboard templates and examples
- 📚 Documentation improvements
- 🧪 Testing with different account types
- 🌍 Support for different tariff structures

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

**Disclaimer:** This is an unofficial integration. Not affiliated with, endorsed by, or supported by OVO Energy Australia.

---

## 🔗 Links

- **GitHub Repository:** https://github.com/HallyAus/OVO_Aus_api
- **Issues & Support:** https://github.com/HallyAus/OVO_Aus_api/issues
- **OVO Energy Australia:** https://www.ovoenergy.com.au
- **Home Assistant:** https://www.home-assistant.io

---

## 🙏 Credits

**Developed by:** HallyAus with Claude (Sonnet 4.5)
**License:** MIT
**Status:** Active Development

### Acknowledgments

- OVO Energy Australia for their excellent solar tracking platform
- Home Assistant community for integration patterns and support
- All contributors and users who provide feedback

---

<div align="center">

**Made with ☀️ for the Australian solar community**

⭐ If you find this useful, please star the repository! ⭐

</div>
