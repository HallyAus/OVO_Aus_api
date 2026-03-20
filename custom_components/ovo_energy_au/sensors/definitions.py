"""Data-driven sensor definitions for OVO Energy Australia.

Instead of 80+ inline OVOEnergyAUSensor() constructor calls, sensors are
defined as simple dicts and instantiated in a loop. This makes it trivial
to add/remove/modify sensors without touching constructor code.
"""

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy

from .base import get_yesterday_hourly_data

# Each entry: (key, name, unit, device_class, state_class, icon, value_fn, device_category)
# value_fn receives the coordinator.data dict

ENERGY_SENSORS = [
    # ── Yesterday ──
    ("daily_solar_consumption", "Solar Consumption", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, "mdi:solar-power",
     lambda d: d.get("daily", {}).get("solar_consumption"), "Yesterday"),

    ("daily_grid_consumption", "Grid Consumption", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, "mdi:transmission-tower",
     lambda d: d.get("daily", {}).get("grid_consumption"), "Yesterday"),

    ("daily_return_to_grid", "Return to Grid", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, "mdi:transmission-tower-export",
     lambda d: d.get("daily", {}).get("return_to_grid"), "Yesterday"),

    ("daily_solar_charge", "Solar Feed-in Credit", "AUD",
     SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "mdi:cash-plus",
     lambda d: d.get("daily", {}).get("solar_charge"), "Yesterday"),

    ("daily_grid_charge", "Grid Charge", "AUD",
     SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "mdi:currency-usd",
     lambda d: d.get("daily", {}).get("grid_charge"), "Yesterday"),

    ("daily_return_to_grid_charge", "Return to Grid Charge", "AUD",
     SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "mdi:currency-usd",
     lambda d: d.get("daily", {}).get("return_to_grid_charge"), "Yesterday"),

    # ── This Month ──
    ("monthly_solar_consumption", "Solar Consumption", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, "mdi:solar-power",
     lambda d: d.get("monthly", {}).get("solar_consumption"), "This Month"),

    ("monthly_grid_consumption", "Grid Consumption", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, "mdi:transmission-tower",
     lambda d: d.get("monthly", {}).get("grid_consumption"), "This Month"),

    ("monthly_return_to_grid", "Return to Grid", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, "mdi:transmission-tower-export",
     lambda d: d.get("monthly", {}).get("return_to_grid"), "This Month"),

    ("monthly_solar_charge", "Solar Feed-in Credit", "AUD",
     SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "mdi:cash-plus",
     lambda d: d.get("monthly", {}).get("solar_charge"), "This Month"),

    ("monthly_grid_charge", "Grid Charge", "AUD",
     SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "mdi:currency-usd",
     lambda d: d.get("monthly", {}).get("grid_charge"), "This Month"),

    ("monthly_return_to_grid_charge", "Return to Grid Charge", "AUD",
     SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "mdi:currency-usd",
     lambda d: d.get("monthly", {}).get("return_to_grid_charge"), "This Month"),

    # ── This Year ──
    ("yearly_solar_consumption", "Solar Consumption", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, "mdi:solar-power",
     lambda d: d.get("yearly", {}).get("solar_consumption"), "This Year"),

    ("yearly_grid_consumption", "Grid Consumption", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, "mdi:transmission-tower",
     lambda d: d.get("yearly", {}).get("grid_consumption"), "This Year"),

    ("yearly_grid_charge", "Grid Charge", "AUD",
     SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "mdi:currency-usd",
     lambda d: d.get("yearly", {}).get("grid_charge"), "This Year"),

    # ── Last Week ──
    ("last_7_days_solar_consumption", "Solar Consumption", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, "mdi:solar-power",
     lambda d: d.get("last_7_days", {}).get("solar_consumption"), "Last Week"),

    ("last_7_days_grid_consumption", "Grid Consumption", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, "mdi:transmission-tower",
     lambda d: d.get("last_7_days", {}).get("grid_consumption"), "Last Week"),

    ("last_7_days_solar_charge", "Solar Feed-in Credit", "AUD",
     SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "mdi:cash-plus",
     lambda d: d.get("last_7_days", {}).get("solar_charge"), "Last Week"),

    ("last_7_days_grid_charge", "Grid Charge", "AUD",
     SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "mdi:currency-usd",
     lambda d: d.get("last_7_days", {}).get("grid_charge"), "Last Week"),

    # ── Last Month ──
    ("last_month_solar_consumption", "Solar Consumption", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, "mdi:solar-power",
     lambda d: d.get("last_month", {}).get("solar_consumption"), "Last Month"),

    ("last_month_grid_consumption", "Grid Consumption", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, "mdi:transmission-tower",
     lambda d: d.get("last_month", {}).get("grid_consumption"), "Last Month"),

    ("last_month_solar_charge", "Solar Feed-in Credit", "AUD",
     SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "mdi:cash-plus",
     lambda d: d.get("last_month", {}).get("solar_charge"), "Last Month"),

    ("last_month_grid_charge", "Grid Charge", "AUD",
     SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "mdi:currency-usd",
     lambda d: d.get("last_month", {}).get("grid_charge"), "Last Month"),

    # ── Month to Date ──
    ("month_to_date_solar_consumption", "Solar Consumption", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, "mdi:solar-power",
     lambda d: d.get("month_to_date", {}).get("solar_consumption"), "Month to Date"),

    ("month_to_date_grid_consumption", "Grid Consumption", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, "mdi:transmission-tower",
     lambda d: d.get("month_to_date", {}).get("grid_consumption"), "Month to Date"),

    ("month_to_date_solar_charge", "Solar Feed-in Credit", "AUD",
     SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "mdi:cash-plus",
     lambda d: d.get("month_to_date", {}).get("solar_charge"), "Month to Date"),

    ("month_to_date_grid_charge", "Grid Charge", "AUD",
     SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "mdi:currency-usd",
     lambda d: d.get("month_to_date", {}).get("grid_charge"), "Month to Date"),
]

ANALYTICS_SENSORS = [
    # Peak Usage
    ("peak_4hour_consumption", "Peak 4-Hour Consumption", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, None, "mdi:chart-bell-curve",
     lambda d: (p := d.get("hourly", {}).get("peak_4hour_window")) and p.get("total_consumption"),
     "Peak Usage"),

    # Week Comparison
    ("week_comparison_solar", "Solar Consumption (This Week)", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, None, "mdi:compare-horizontal",
     lambda d: d.get("week_comparison", {}).get("this_week_solar"), "Week Comparison"),

    ("week_comparison_grid", "Grid Consumption (This Week)", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, None, "mdi:compare-horizontal",
     lambda d: d.get("week_comparison", {}).get("this_week_grid"), "Week Comparison"),

    ("week_comparison_cost", "Cost (This Week)", "AUD",
     SensorDeviceClass.MONETARY, None, "mdi:compare-horizontal",
     lambda d: d.get("week_comparison", {}).get("this_week_cost"), "Week Comparison"),

    ("week_comparison_solar_change_pct", "Solar Change %", "%",
     None, None, "mdi:percent",
     lambda d: d.get("week_comparison", {}).get("solar_change_pct"), "Week Comparison"),

    ("week_comparison_grid_change_pct", "Grid Change %", "%",
     None, None, "mdi:percent",
     lambda d: d.get("week_comparison", {}).get("grid_change_pct"), "Week Comparison"),

    ("week_comparison_cost_change_pct", "Cost Change %", "%",
     None, None, "mdi:percent",
     lambda d: d.get("week_comparison", {}).get("cost_change_pct"), "Week Comparison"),

    # Weekday vs Weekend
    ("weekday_avg_consumption", "Avg Daily Consumption (Weekday)", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, None, "mdi:calendar-week",
     lambda d: d.get("weekday_analysis", {}).get("avg_solar", 0) + d.get("weekday_analysis", {}).get("avg_grid", 0),
     "Weekday vs Weekend"),

    ("weekend_avg_consumption", "Avg Daily Consumption (Weekend)", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, None, "mdi:calendar-weekend",
     lambda d: d.get("weekend_analysis", {}).get("avg_solar", 0) + d.get("weekend_analysis", {}).get("avg_grid", 0),
     "Weekday vs Weekend"),

    ("weekday_avg_cost", "Avg Daily Cost (Weekday)", "AUD",
     SensorDeviceClass.MONETARY, None, "mdi:calendar-week",
     lambda d: d.get("weekday_analysis", {}).get("avg_cost"), "Weekday vs Weekend"),

    ("weekend_avg_cost", "Avg Daily Cost (Weekend)", "AUD",
     SensorDeviceClass.MONETARY, None, "mdi:calendar-weekend",
     lambda d: d.get("weekend_analysis", {}).get("avg_cost"), "Weekday vs Weekend"),

    # Self-Sufficiency
    ("self_sufficiency_score", "Self-Sufficiency Score", "%",
     None, None, "mdi:battery-charging-100",
     lambda d: d.get("self_sufficiency", {}).get("score"), "Solar Insights"),

    # High Usage Days
    ("high_usage_days", "High Usage Days Tracker", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, None, "mdi:medal",
     lambda d: d.get("high_usage_days", [{}])[0].get("total_consumption") if d.get("high_usage_days") else None,
     "Usage Rankings"),

    # Hourly Heatmap
    ("hourly_heatmap", "Hourly Usage Heatmap", None,
     None, None, "mdi:grid",
     lambda d: len(d.get("hourly", {}).get("hourly_heatmap", {})), "Usage Patterns"),

    # Hourly Data Totals
    ("hourly_solar_total", "Hourly Solar Total (Last 7 Days)", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, None, "mdi:solar-power",
     lambda d: d.get("hourly", {}).get("solar_total", 0), "Hourly Data"),

    ("hourly_grid_total", "Hourly Grid Total (Last 7 Days)", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, None, "mdi:transmission-tower",
     lambda d: d.get("hourly", {}).get("grid_total", 0), "Hourly Data"),

    ("hourly_return_to_grid_total", "Hourly Return to Grid Total (Last 7 Days)", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, None, "mdi:transmission-tower-export",
     lambda d: d.get("hourly", {}).get("return_to_grid_total", 0), "Hourly Data"),

    ("hourly_data_entry_count", "Hourly Data Entries", None,
     None, None, "mdi:counter",
     lambda d: sum(len(d.get("hourly", {}).get(k, [])) for k in ["solar_entries", "grid_entries", "return_to_grid_entries"]),
     "Hourly Data"),

    # Yesterday Hourly
    ("hourly_solar_yesterday", "Yesterday Solar Hourly", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, None, "mdi:solar-power",
     lambda d: get_yesterday_hourly_data(d, "solar_entries")["state"], "Hourly Graph Data"),

    ("hourly_grid_yesterday", "Yesterday Grid Hourly", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, None, "mdi:transmission-tower",
     lambda d: get_yesterday_hourly_data(d, "grid_entries")["state"], "Hourly Graph Data"),

    ("hourly_export_yesterday", "Yesterday Export Hourly", UnitOfEnergy.KILO_WATT_HOUR,
     SensorDeviceClass.ENERGY, None, "mdi:transmission-tower-export",
     lambda d: get_yesterday_hourly_data(d, "return_to_grid_entries")["state"], "Hourly Graph Data"),

    # Cost Analysis
    ("cost_per_kwh_overall", "Overall Cost per kWh", "AUD/kWh",
     None, None, "mdi:currency-usd",
     lambda d: d.get("cost_per_kwh", {}).get("overall"), "Cost Analysis"),

    ("cost_per_kwh_grid", "Grid Cost per kWh", "AUD/kWh",
     None, None, "mdi:transmission-tower",
     lambda d: d.get("cost_per_kwh", {}).get("grid"), "Cost Analysis"),

    ("cost_per_kwh_solar", "Solar Cost per kWh", "AUD/kWh",
     None, None, "mdi:solar-power",
     lambda d: d.get("cost_per_kwh", {}).get("solar"), "Cost Analysis"),

    # Monthly Projection
    ("monthly_projection_total", "Projected Monthly Cost", "AUD",
     SensorDeviceClass.MONETARY, None, "mdi:crystal-ball",
     lambda d: d.get("monthly_projection", {}).get("projected_total"), "Monthly Forecast"),

    ("monthly_projection_remaining", "Projected Remaining Cost", "AUD",
     SensorDeviceClass.MONETARY, None, "mdi:calendar-clock",
     lambda d: d.get("monthly_projection", {}).get("projected_remaining"), "Monthly Forecast"),

    ("monthly_daily_average", "Daily Average Cost", "AUD",
     SensorDeviceClass.MONETARY, None, "mdi:chart-line",
     lambda d: d.get("monthly_projection", {}).get("daily_average"), "Monthly Forecast"),

    # Solar Export
    ("rtg_export_credit", "Export Credit Earned", "AUD",
     SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "mdi:cash-multiple",
     lambda d: d.get("return_to_grid_analysis", {}).get("export_credit"), "Solar Export"),

    ("rtg_export_rate", "Export Rate per kWh", "AUD/kWh",
     None, None, "mdi:cash-check",
     lambda d: d.get("return_to_grid_analysis", {}).get("export_rate_per_kwh"), "Solar Export"),

    ("rtg_potential_savings", "Potential Savings (vs Purchase)", "AUD",
     SensorDeviceClass.MONETARY, None, "mdi:piggy-bank",
     lambda d: d.get("return_to_grid_analysis", {}).get("potential_savings"), "Solar Export"),

    ("rtg_opportunity_cost", "Opportunity Cost", "AUD",
     SensorDeviceClass.MONETARY, None, "mdi:alert-circle",
     lambda d: d.get("return_to_grid_analysis", {}).get("opportunity_cost"), "Solar Export"),
]

# Rate types for per-day breakdown sensors
RATE_TYPES = ["PEAK", "SHOULDER", "OFFPEAK", "EV_OFFPEAK", "OTHER", "FREE_3"]

RATE_TYPE_ICONS = {
    "PEAK": "mdi:arrow-up-bold",
    "SHOULDER": "mdi:minus",
    "OFFPEAK": "mdi:arrow-down-bold",
    "EV_OFFPEAK": "mdi:ev-station",
    "FREE_3": "mdi:gift",
    "OTHER": "mdi:chart-bar",
}


def get_rate_value(data: dict, period: str, rate_type: str, metric: str) -> float | None:
    """Extract rate breakdown value safely."""
    if not data:
        return None
    rate_data = data.get(period, {}).get("rate_breakdown", {}).get(rate_type, {})
    if not rate_data.get("available"):
        return None
    return rate_data.get(metric)


def calculate_free_savings(data: dict, period: str, coordinator) -> float | None:
    """Calculate savings from free period consumption."""
    free_consumption = get_rate_value(data, period, "FREE_3", "consumption")
    if not free_consumption:
        return None

    other_charge = get_rate_value(data, period, "OTHER", "charge")
    other_consumption = get_rate_value(data, period, "OTHER", "consumption")

    if other_charge and other_consumption and other_consumption > 0:
        return round(free_consumption * (other_charge / other_consumption), 2)

    return round(free_consumption * coordinator.plan_config.shoulder_rate, 2)
