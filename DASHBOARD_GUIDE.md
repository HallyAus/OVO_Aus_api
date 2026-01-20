# OVO Energy Australia Dashboard Guide

This integration provides comprehensive energy monitoring with daily breakdown data for graphing monthly charges similar to the OVO Energy dashboard.

## Available Sensors

### Daily Sensors (Today's Usage)
- `sensor.daily_solar_consumption` - Solar energy consumed today (kWh)
- `sensor.daily_grid_consumption` - Grid energy consumed today (kWh)
- `sensor.daily_return_to_grid` - Energy exported to grid today (kWh)
- `sensor.daily_solar_charge` - Cost of solar today ($)
- `sensor.daily_grid_charge` - Cost of grid today ($)
- `sensor.daily_return_to_grid_charge` - Credit from exports today ($)

### Monthly Sensors (Current Month)
- `sensor.monthly_solar_consumption` - Total solar this month (kWh)
- `sensor.monthly_grid_consumption` - Total grid this month (kWh)
- `sensor.monthly_return_to_grid` - Total exports this month (kWh)
- `sensor.monthly_solar_charge` - Total solar cost this month ($)
- `sensor.monthly_grid_charge` - Total grid cost this month ($)
- `sensor.monthly_return_to_grid_charge` - Total export credit this month ($)

**Monthly sensors include daily breakdown attributes:**
- `daily_breakdown` - Array of daily entries with date, consumption, and charge
- `days_in_month` - Number of days tracked
- `daily_average` - Average consumption per day
- `daily_max` - Maximum consumption in a single day
- `daily_charge_average` - Average cost per day

### Yearly Sensors
- `sensor.yearly_solar_consumption` - Total solar this year (kWh)
- `sensor.yearly_grid_consumption` - Total grid this year (kWh)
- `sensor.yearly_grid_charge` - Total grid cost this year ($)

### Hourly Sensors (Last 7 Days)
- `sensor.hourly_solar_consumption` - Total solar over 7 days (kWh)
- `sensor.hourly_grid_consumption` - Total grid over 7 days (kWh)
- `sensor.hourly_return_to_grid` - Total exports over 7 days (kWh)

**Hourly sensors include entry arrays for detailed graphing:**
- `entries` - Array of hourly data points with timestamps
- `entry_count` - Number of hourly records

## Dashboard Options

### Option 1: Advanced Dashboard with Graphs (Recommended)
**File:** `dashboard_monthly_charges.yaml`

**Features:**
- Daily bar charts for solar consumption (like OVO dashboard)
- Daily bar charts for solar and grid charges
- Combined solar vs grid comparison
- Monthly statistics summary
- Requires: [ApexCharts Card](https://github.com/RomRider/apexcharts-card)

**Installation:**
1. Install ApexCharts card via HACS
2. Copy `dashboard_monthly_charges.yaml` content
3. Create new dashboard or add to existing one
4. Paste YAML in edit mode

### Option 2: Simple Dashboard (Built-in Cards)
**File:** `dashboard_simple.yaml`

**Features:**
- Monthly totals and statistics
- Daily averages
- Period comparisons
- No custom components required
- Uses only built-in Home Assistant cards

**Installation:**
1. Copy `dashboard_simple.yaml` content
2. Create new dashboard or add to existing one
3. Paste YAML in edit mode

## Daily Breakdown Data Structure

The `daily_breakdown` attribute on monthly sensors provides day-by-day data:

```json
{
  "daily_breakdown": [
    {
      "date": "2026-01-01",
      "day": 1,
      "consumption": 35.24,
      "charge": 0.99,
      "read_type": "ACTUAL"
    },
    {
      "date": "2026-01-02",
      "day": 2,
      "consumption": 32.15,
      "charge": 0.85,
      "read_type": "ACTUAL"
    }
    // ... one entry per day
  ],
  "days_in_month": 20,
  "daily_average": 34.5,
  "daily_max": 45.2,
  "daily_charge_average": 1.05
}
```

## Using Daily Breakdown in Custom Cards

### Example 1: ApexCharts Bar Chart
```yaml
type: custom:apexcharts-card
header:
  title: Daily Solar Consumption
series:
  - entity: sensor.monthly_solar_consumption
    name: Solar kWh
    type: column
    color: orange
    data_generator: |
      const daily = entity.attributes.daily_breakdown || [];
      return daily.map(day => {
        return [new Date(day.date).getTime(), day.consumption];
      });
```

### Example 2: Template Sensor for Today's Data
```yaml
template:
  - sensor:
      - name: "Today Solar Charge"
        state: >
          {% set today = now().strftime('%Y-%m-%d') %}
          {% set breakdown = state_attr('sensor.monthly_solar_charge', 'daily_breakdown') %}
          {% if breakdown %}
            {% set today_data = breakdown | selectattr('date', 'eq', today) | list %}
            {% if today_data %}
              {{ today_data[0].charge }}
            {% else %}
              0
            {% endif %}
          {% else %}
            0
          {% endif %}
        unit_of_measurement: 'AUD'
```

### Example 3: Markdown Card with Daily Breakdown Table
```yaml
type: markdown
content: |
  ## Daily Solar Breakdown
  {% set breakdown = state_attr('sensor.monthly_solar_consumption', 'daily_breakdown') %}
  {% if breakdown %}
  | Date | kWh | Cost |
  |------|-----|------|
  {% for day in breakdown[-7:] %}
  | {{ day.date }} | {{ day.consumption | round(2) }} | ${{ day.charge | round(2) }} |
  {% endfor %}
  {% else %}
  No data available
  {% endif %}
```

## Graph Examples

### Monthly Solar Cost Trend
Shows how your solar costs vary day-by-day throughout the month, just like the OVO dashboard.

### Solar vs Grid Comparison
Stacked or grouped bar chart comparing daily solar and grid consumption.

### Running Total
Line chart showing cumulative consumption/cost throughout the month.

## Tips for Best Results

1. **Data Updates:** Sensors update every 5 minutes with fresh data from OVO's API
2. **Historical Data:** Hourly sensors fetch 7 days of history to work around API limitations
3. **Monthly Reset:** Daily breakdown resets at the start of each month
4. **Graph Refresh:** Graphs update automatically when sensor data changes
5. **Missing Days:** If integration was offline, some days may be missing from breakdown

## Customization Ideas

1. **Color Coding:** Use red for high costs, green for low costs
2. **Alerts:** Create automations when daily cost exceeds threshold
3. **Comparisons:** Compare this month vs last month using templates
4. **Export:** Use the data in Node-RED or other automation platforms
5. **Energy Dashboard:** Add to Home Assistant Energy dashboard for unified view

## Troubleshooting

**Q: Daily breakdown is empty**
A: Wait for next data refresh (5 minutes). Check that monthly sensor has data.

**Q: Graphs don't show data**
A: Ensure ApexCharts card is installed. Check browser console for errors.

**Q: Some days are missing**
A: Normal if integration was added mid-month. Will populate over time.

**Q: Statistics show 0**
A: Need at least one day of data for statistics to calculate.

## Support

For issues or questions:
- GitHub: https://github.com/HallyAus/OVO_Aus_api/issues
- Check logs: Settings → System → Logs → Filter by "ovo_energy"
