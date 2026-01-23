"""Sensor platform for OVO Energy Australia."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _get_rate_value(data: dict, period: str, rate_type: str, metric: str) -> float | None:
    """Extract rate breakdown value safely.

    Args:
        data: Coordinator data dict
        period: "daily", "monthly", or "yearly"
        rate_type: "EV_OFFPEAK", "FREE_3", or "OTHER"
        metric: "consumption", "charge", or "percent"

    Returns:
        Value if available, None otherwise
    """
    if not data:
        return None

    period_data = data.get(period, {})
    rate_breakdown = period_data.get("rate_breakdown", {})
    rate_data = rate_breakdown.get(rate_type, {})

    if not rate_data.get("available"):
        return None

    return rate_data.get(metric)


def _calculate_free_savings(data: dict, period: str, coordinator) -> float | None:
    """Calculate savings from free period.

    Estimates what would have been charged at shoulder rate.
    """
    if not data:
        return None

    # Get FREE_3 consumption
    free_consumption = _get_rate_value(data, period, "FREE_3", "consumption")
    if not free_consumption:
        return None

    # Estimate rate from OTHER consumption (if available)
    other_charge = _get_rate_value(data, period, "OTHER", "charge")
    other_consumption = _get_rate_value(data, period, "OTHER", "consumption")

    if other_charge and other_consumption and other_consumption > 0:
        estimated_rate = other_charge / other_consumption
        return round(free_consumption * estimated_rate, 2)

    # Fallback to configured shoulder rate
    shoulder_rate = coordinator.plan_config.get("shoulder_rate", 0.25)
    return round(free_consumption * shoulder_rate, 2)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OVO Energy Australia sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        # Yesterday's Data (available at 6am)
        OVOEnergyAUSensor(
            coordinator,
            "daily_solar_consumption",
            "Solar Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:solar-power",
            lambda data: data.get("daily", {}).get("solar_consumption"),
            "Yesterday",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "daily_grid_consumption",
            "Grid Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:transmission-tower",
            lambda data: data.get("daily", {}).get("grid_consumption"),
            "Yesterday",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "daily_return_to_grid",
            "Return to Grid",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:transmission-tower-export",
            lambda data: data.get("daily", {}).get("return_to_grid"),
            "Yesterday",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "daily_solar_charge",
            "Solar Feed-in Credit",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:cash-plus",
            lambda data: data.get("daily", {}).get("solar_charge"),
            "Yesterday",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "daily_grid_charge",
            "Grid Charge",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("daily", {}).get("grid_charge"),
            "Yesterday",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "daily_return_to_grid_charge",
            "Return to Grid Charge",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("daily", {}).get("return_to_grid_charge"),
            "Yesterday",
        ),
        # This Month (current billing month)
        OVOEnergyAUSensor(
            coordinator,
            "monthly_solar_consumption",
            "Solar Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:solar-power",
            lambda data: data.get("monthly", {}).get("solar_consumption"),
            "This Month",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_grid_consumption",
            "Grid Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:transmission-tower",
            lambda data: data.get("monthly", {}).get("grid_consumption"),
            "This Month",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_return_to_grid",
            "Return to Grid",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:transmission-tower-export",
            lambda data: data.get("monthly", {}).get("return_to_grid"),
            "This Month",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_solar_charge",
            "Solar Feed-in Credit",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:cash-plus",
            lambda data: data.get("monthly", {}).get("solar_charge"),
            "This Month",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_grid_charge",
            "Grid Charge",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("monthly", {}).get("grid_charge"),
            "This Month",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_return_to_grid_charge",
            "Return to Grid Charge",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("monthly", {}).get("return_to_grid_charge"),
            "This Month",
        ),
        # This Year
        OVOEnergyAUSensor(
            coordinator,
            "yearly_solar_consumption",
            "Solar Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:solar-power",
            lambda data: data.get("yearly", {}).get("solar_consumption"),
            "This Year",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "yearly_grid_consumption",
            "Grid Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:transmission-tower",
            lambda data: data.get("yearly", {}).get("grid_consumption"),
            "This Year",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "yearly_grid_charge",
            "Grid Charge",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("yearly", {}).get("grid_charge"),
            "This Year",
        ),
        # Hourly Data (Last 7 Days)
        OVOEnergyAUSensor(
            coordinator,
            "hourly_solar_consumption",
            "Solar Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            None,  # Not a total, just current value
            "mdi:solar-power",
            lambda data: data.get("hourly", {}).get("solar_total"),
            "Hourly Data (Last 7 Days)",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "hourly_grid_consumption",
            "Grid Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            None,  # Not a total, just current value
            "mdi:transmission-tower",
            lambda data: data.get("hourly", {}).get("grid_total"),
            "Hourly Data (Last 7 Days)",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "hourly_return_to_grid",
            "Return to Grid",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            None,  # Not a total, just current value
            "mdi:transmission-tower-export",
            lambda data: data.get("hourly", {}).get("return_to_grid_total"),
            "Hourly Data (Last 7 Days)",
        ),
        # Last Week Total
        OVOEnergyAUSensor(
            coordinator,
            "last_7_days_solar_consumption",
            "Solar Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:solar-power",
            lambda data: data.get("last_7_days", {}).get("solar_consumption"),
            "Last Week",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "last_7_days_grid_consumption",
            "Grid Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:transmission-tower",
            lambda data: data.get("last_7_days", {}).get("grid_consumption"),
            "Last Week",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "last_7_days_solar_charge",
            "Solar Feed-in Credit",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:cash-plus",
            lambda data: data.get("last_7_days", {}).get("solar_charge"),
            "Last Week",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "last_7_days_grid_charge",
            "Grid Charge",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("last_7_days", {}).get("grid_charge"),
            "Last Week",
        ),
        # Last Month Total
        OVOEnergyAUSensor(
            coordinator,
            "last_month_solar_consumption",
            "Solar Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:solar-power",
            lambda data: data.get("last_month", {}).get("solar_consumption"),
            "Last Month",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "last_month_grid_consumption",
            "Grid Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:transmission-tower",
            lambda data: data.get("last_month", {}).get("grid_consumption"),
            "Last Month",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "last_month_solar_charge",
            "Solar Feed-in Credit",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:cash-plus",
            lambda data: data.get("last_month", {}).get("solar_charge"),
            "Last Month",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "last_month_grid_charge",
            "Grid Charge",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("last_month", {}).get("grid_charge"),
            "Last Month",
        ),
        # Month to Date
        OVOEnergyAUSensor(
            coordinator,
            "month_to_date_solar_consumption",
            "Solar Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:solar-power",
            lambda data: data.get("month_to_date", {}).get("solar_consumption"),
            "Month to Date",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "month_to_date_grid_consumption",
            "Grid Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:transmission-tower",
            lambda data: data.get("month_to_date", {}).get("grid_consumption"),
            "Month to Date",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "month_to_date_solar_charge",
            "Solar Feed-in Credit",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:cash-plus",
            lambda data: data.get("month_to_date", {}).get("solar_charge"),
            "Month to Date",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "month_to_date_grid_charge",
            "Grid Charge",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("month_to_date", {}).get("grid_charge"),
            "Month to Date",
        ),

        # ====================
        # ADVANCED ANALYTICS (10 New Features)
        # ====================

        # Feature 1: Peak Usage Time Blocks
        OVOEnergyAUSensor(
            coordinator,
            "peak_4hour_consumption",
            "Peak 4-Hour Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            None,
            "mdi:chart-bell-curve",
            lambda data: (peak := data.get("hourly", {}).get("peak_4hour_window")) and peak.get("total_consumption"),
            "Peak Usage",
        ),

        # Feature 2: Week-over-Week Comparison
        OVOEnergyAUSensor(
            coordinator,
            "week_comparison_solar",
            "Solar Consumption (This Week)",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:compare-horizontal",
            lambda data: data.get("week_comparison", {}).get("this_week_solar"),
            "Week Comparison",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "week_comparison_grid",
            "Grid Consumption (This Week)",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:compare-horizontal",
            lambda data: data.get("week_comparison", {}).get("this_week_grid"),
            "Week Comparison",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "week_comparison_cost",
            "Cost (This Week)",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:compare-horizontal",
            lambda data: data.get("week_comparison", {}).get("this_week_cost"),
            "Week Comparison",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "week_comparison_solar_change_pct",
            "Solar Change %",
            "%",
            None,
            None,
            "mdi:percent",
            lambda data: data.get("week_comparison", {}).get("solar_change_pct"),
            "Week Comparison",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "week_comparison_grid_change_pct",
            "Grid Change %",
            "%",
            None,
            None,
            "mdi:percent",
            lambda data: data.get("week_comparison", {}).get("grid_change_pct"),
            "Week Comparison",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "week_comparison_cost_change_pct",
            "Cost Change %",
            "%",
            None,
            None,
            "mdi:percent",
            lambda data: data.get("week_comparison", {}).get("cost_change_pct"),
            "Week Comparison",
        ),

        # Feature 3: Weekday vs Weekend Analysis
        OVOEnergyAUSensor(
            coordinator,
            "weekday_avg_consumption",
            "Avg Daily Consumption (Weekday)",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            None,
            "mdi:calendar-week",
            lambda data: data.get("weekday_analysis", {}).get("avg_solar", 0) + data.get("weekday_analysis", {}).get("avg_grid", 0),
            "Weekday vs Weekend",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "weekend_avg_consumption",
            "Avg Daily Consumption (Weekend)",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            None,
            "mdi:calendar-weekend",
            lambda data: data.get("weekend_analysis", {}).get("avg_solar", 0) + data.get("weekend_analysis", {}).get("avg_grid", 0),
            "Weekday vs Weekend",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "weekday_avg_cost",
            "Avg Daily Cost (Weekday)",
            "AUD",
            SensorDeviceClass.MONETARY,
            None,
            "mdi:calendar-week",
            lambda data: data.get("weekday_analysis", {}).get("avg_cost"),
            "Weekday vs Weekend",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "weekend_avg_cost",
            "Avg Daily Cost (Weekend)",
            "AUD",
            SensorDeviceClass.MONETARY,
            None,
            "mdi:calendar-weekend",
            lambda data: data.get("weekend_analysis", {}).get("avg_cost"),
            "Weekday vs Weekend",
        ),

        # Feature 4: Time-of-Use Cost Breakdown
        OVOEnergyAUSensor(
            coordinator,
            "tou_peak_consumption",
            "Peak Period Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:chart-timeline-variant",
            lambda data: data.get("hourly", {}).get("time_of_use", {}).get("peak", {}).get("consumption"),
            "Time of Use",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "tou_shoulder_consumption",
            "Shoulder Period Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:chart-timeline-variant",
            lambda data: data.get("hourly", {}).get("time_of_use", {}).get("shoulder", {}).get("consumption"),
            "Time of Use",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "tou_off_peak_consumption",
            "Off-Peak Period Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:chart-timeline-variant",
            lambda data: data.get("hourly", {}).get("time_of_use", {}).get("off_peak", {}).get("consumption"),
            "Time of Use",
        ),

        # Super Off-Peak Tracking (Free 3 & EV Plans - 11am-2pm free period)
        OVOEnergyAUSensor(
            coordinator,
            "super_off_peak_consumption",
            "Super Off-Peak Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:lightning-bolt",
            lambda data: data.get("hourly", {}).get("free_usage", {}).get("consumption"),
            "Super Off-Peak",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "super_off_peak_cost_saved",
            "Super Off-Peak Cost Saved",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:piggy-bank",
            lambda data: data.get("hourly", {}).get("free_usage", {}).get("cost_saved"),
            "Super Off-Peak",
        ),

        # EV Off-Peak - Weekly (Last 7 Days)
        OVOEnergyAUSensor(
            coordinator,
            "ev_off_peak_weekly_consumption",
            "EV Off-Peak Consumption (Weekly)",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:ev-station",
            lambda data: data.get("hourly", {}).get("ev_usage_weekly", {}).get("consumption"),
            "EV Off-Peak - Weekly",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "ev_off_peak_weekly_cost",
            "EV Off-Peak Cost (Weekly)",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("hourly", {}).get("ev_usage_weekly", {}).get("cost"),
            "EV Off-Peak - Weekly",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "ev_off_peak_weekly_savings",
            "EV Off-Peak Savings (Weekly)",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:cash-plus",
            lambda data: data.get("hourly", {}).get("ev_usage_weekly", {}).get("cost_saved"),
            "EV Off-Peak - Weekly",
        ),

        # EV Off-Peak - Monthly (Month to Date)
        OVOEnergyAUSensor(
            coordinator,
            "ev_off_peak_monthly_consumption",
            "EV Off-Peak Consumption (Monthly)",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:ev-station",
            lambda data: data.get("hourly", {}).get("ev_usage_monthly", {}).get("consumption"),
            "EV Off-Peak - Monthly",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "ev_off_peak_monthly_cost",
            "EV Off-Peak Cost (Monthly)",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("hourly", {}).get("ev_usage_monthly", {}).get("cost"),
            "EV Off-Peak - Monthly",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "ev_off_peak_monthly_savings",
            "EV Off-Peak Savings (Monthly)",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:cash-plus",
            lambda data: data.get("hourly", {}).get("ev_usage_monthly", {}).get("cost_saved"),
            "EV Off-Peak - Monthly",
        ),

        # EV Off-Peak - Yearly (Year to Date)
        OVOEnergyAUSensor(
            coordinator,
            "ev_off_peak_yearly_consumption",
            "EV Off-Peak Consumption (Yearly)",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:ev-station",
            lambda data: data.get("hourly", {}).get("ev_usage_yearly", {}).get("consumption"),
            "EV Off-Peak - Yearly",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "ev_off_peak_yearly_cost",
            "EV Off-Peak Cost (Yearly)",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: data.get("hourly", {}).get("ev_usage_yearly", {}).get("cost"),
            "EV Off-Peak - Yearly",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "ev_off_peak_yearly_savings",
            "EV Off-Peak Savings (Yearly)",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:cash-plus",
            lambda data: data.get("hourly", {}).get("ev_usage_yearly", {}).get("cost_saved"),
            "EV Off-Peak - Yearly",
        ),

        # Feature 5: Solar Self-Sufficiency Score
        OVOEnergyAUSensor(
            coordinator,
            "self_sufficiency_score",
            "Self-Sufficiency Score",
            "%",
            None,
            None,
            "mdi:battery-charging-100",
            lambda data: data.get("self_sufficiency", {}).get("score"),
            "Solar Insights",
        ),

        # Feature 6: High Usage Day Rankings (data in attributes)
        OVOEnergyAUSensor(
            coordinator,
            "high_usage_days",
            "High Usage Days Tracker",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            None,
            "mdi:medal",
            lambda data: data.get("high_usage_days", [{}])[0].get("total_consumption") if data.get("high_usage_days") else None,
            "Usage Rankings",
        ),

        # Feature 7: Hourly Heatmap (data in attributes)
        OVOEnergyAUSensor(
            coordinator,
            "hourly_heatmap",
            "Hourly Usage Heatmap",
            None,
            None,
            None,
            "mdi:grid",
            lambda data: len(data.get("hourly", {}).get("hourly_heatmap", {})),
            "Usage Patterns",
        ),

        # Feature 8: Cost Per kWh Tracking
        OVOEnergyAUSensor(
            coordinator,
            "cost_per_kwh_overall",
            "Overall Cost per kWh",
            "AUD/kWh",
            None,
            None,
            "mdi:currency-usd",
            lambda data: data.get("cost_per_kwh", {}).get("overall"),
            "Cost Analysis",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "cost_per_kwh_grid",
            "Grid Cost per kWh",
            "AUD/kWh",
            None,
            None,
            "mdi:transmission-tower",
            lambda data: data.get("cost_per_kwh", {}).get("grid"),
            "Cost Analysis",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "cost_per_kwh_solar",
            "Solar Cost per kWh",
            "AUD/kWh",
            None,
            None,
            "mdi:solar-power",
            lambda data: data.get("cost_per_kwh", {}).get("solar"),
            "Cost Analysis",
        ),

        # Feature 9: Monthly Cost Projection
        OVOEnergyAUSensor(
            coordinator,
            "monthly_projection_total",
            "Projected Monthly Cost",
            "AUD",
            SensorDeviceClass.MONETARY,
            None,
            "mdi:crystal-ball",
            lambda data: data.get("monthly_projection", {}).get("projected_total"),
            "Monthly Forecast",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_projection_remaining",
            "Projected Remaining Cost",
            "AUD",
            SensorDeviceClass.MONETARY,
            None,
            "mdi:calendar-clock",
            lambda data: data.get("monthly_projection", {}).get("projected_remaining"),
            "Monthly Forecast",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_daily_average",
            "Daily Average Cost",
            "AUD",
            SensorDeviceClass.MONETARY,
            None,
            "mdi:chart-line",
            lambda data: data.get("monthly_projection", {}).get("daily_average"),
            "Monthly Forecast",
        ),

        # Feature 10: Return-to-Grid Value Analysis
        OVOEnergyAUSensor(
            coordinator,
            "rtg_export_credit",
            "Export Credit Earned",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:cash-multiple",
            lambda data: data.get("return_to_grid_analysis", {}).get("export_credit"),
            "Solar Export",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "rtg_export_rate",
            "Export Rate per kWh",
            "AUD/kWh",
            None,
            None,
            "mdi:cash-check",
            lambda data: data.get("return_to_grid_analysis", {}).get("export_rate_per_kwh"),
            "Solar Export",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "rtg_potential_savings",
            "Potential Savings (vs Purchase)",
            "AUD",
            SensorDeviceClass.MONETARY,
            None,
            "mdi:piggy-bank",
            lambda data: data.get("return_to_grid_analysis", {}).get("potential_savings"),
            "Solar Export",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "rtg_opportunity_cost",
            "Opportunity Cost",
            "AUD",
            SensorDeviceClass.MONETARY,
            None,
            "mdi:alert-circle",
            lambda data: data.get("return_to_grid_analysis", {}).get("opportunity_cost"),
            "Solar Export",
        ),
    ]

    # Add dynamic sensors for last 3 days
    last_3_days_data = coordinator.data.get("last_3_days", []) if coordinator.data else []
    for idx, day_data in enumerate(last_3_days_data):
        day_num = idx + 1
        sensors.extend([
            OVOEnergyAUDaySensor(
                coordinator,
                f"day_{day_num}_solar_consumption",
                "Solar Consumption",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
                "mdi:solar-power",
                idx,
                "solar_consumption",
            ),
            OVOEnergyAUDaySensor(
                coordinator,
                f"day_{day_num}_solar_charge",
                "Solar Feed-in Credit",
                "AUD",
                SensorDeviceClass.MONETARY,
                SensorStateClass.TOTAL,
                "mdi:cash-plus",
                idx,
                "solar_charge",
            ),
            OVOEnergyAUDaySensor(
                coordinator,
                f"day_{day_num}_grid_consumption",
                "Grid Consumption",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
                "mdi:transmission-tower",
                idx,
                "grid_consumption",
            ),
            OVOEnergyAUDaySensor(
                coordinator,
                f"day_{day_num}_grid_charge",
                "Grid Charge",
                "AUD",
                SensorDeviceClass.MONETARY,
                SensorStateClass.TOTAL,
                "mdi:currency-usd",
                idx,
                "grid_charge",
            ),
        ])

    # ====================
    # RATE BREAKDOWN SENSORS (API-based from rates[] array)
    # ====================

    # Daily Rate Breakdown (Yesterday)
    sensors.extend([
        OVOEnergyAUSensor(
            coordinator,
            "daily_ev_offpeak_consumption",
            "EV Off-Peak Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:ev-station",
            lambda data: _get_rate_value(data, "daily", "EV_OFFPEAK", "consumption"),
            "Rate Breakdown - Yesterday",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "daily_ev_offpeak_cost",
            "EV Off-Peak Cost",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: _get_rate_value(data, "daily", "EV_OFFPEAK", "charge"),
            "Rate Breakdown - Yesterday",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "daily_free_3_consumption",
            "Free Period Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:gift",
            lambda data: _get_rate_value(data, "daily", "FREE_3", "consumption"),
            "Rate Breakdown - Yesterday",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "daily_free_3_savings",
            "Free Period Savings",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:piggy-bank",
            lambda data: _calculate_free_savings(data, "daily", coordinator),
            "Rate Breakdown - Yesterday",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "daily_other_consumption",
            "Other Rates Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:chart-bar",
            lambda data: _get_rate_value(data, "daily", "OTHER", "consumption"),
            "Rate Breakdown - Yesterday",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "daily_other_cost",
            "Other Rates Cost",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: _get_rate_value(data, "daily", "OTHER", "charge"),
            "Rate Breakdown - Yesterday",
        ),
    ])

    # Monthly Rate Breakdown (This Month)
    sensors.extend([
        OVOEnergyAUSensor(
            coordinator,
            "monthly_ev_offpeak_consumption",
            "EV Off-Peak Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:ev-station",
            lambda data: _get_rate_value(data, "monthly", "EV_OFFPEAK", "consumption"),
            "Rate Breakdown - This Month",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_ev_offpeak_cost",
            "EV Off-Peak Cost",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: _get_rate_value(data, "monthly", "EV_OFFPEAK", "charge"),
            "Rate Breakdown - This Month",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_free_3_consumption",
            "Free Period Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:gift",
            lambda data: _get_rate_value(data, "monthly", "FREE_3", "consumption"),
            "Rate Breakdown - This Month",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_free_3_savings",
            "Free Period Savings",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:piggy-bank",
            lambda data: _calculate_free_savings(data, "monthly", coordinator),
            "Rate Breakdown - This Month",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_other_consumption",
            "Other Rates Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:chart-bar",
            lambda data: _get_rate_value(data, "monthly", "OTHER", "consumption"),
            "Rate Breakdown - This Month",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "monthly_other_cost",
            "Other Rates Cost",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: _get_rate_value(data, "monthly", "OTHER", "charge"),
            "Rate Breakdown - This Month",
        ),
    ])

    # Yearly Rate Breakdown (This Year)
    sensors.extend([
        OVOEnergyAUSensor(
            coordinator,
            "yearly_ev_offpeak_consumption",
            "EV Off-Peak Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:ev-station",
            lambda data: _get_rate_value(data, "yearly", "EV_OFFPEAK", "consumption"),
            "Rate Breakdown - This Year",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "yearly_ev_offpeak_cost",
            "EV Off-Peak Cost",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: _get_rate_value(data, "yearly", "EV_OFFPEAK", "charge"),
            "Rate Breakdown - This Year",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "yearly_free_3_consumption",
            "Free Period Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:gift",
            lambda data: _get_rate_value(data, "yearly", "FREE_3", "consumption"),
            "Rate Breakdown - This Year",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "yearly_free_3_savings",
            "Free Period Savings",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:piggy-bank",
            lambda data: _calculate_free_savings(data, "yearly", coordinator),
            "Rate Breakdown - This Year",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "yearly_other_consumption",
            "Other Rates Consumption",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL,
            "mdi:chart-bar",
            lambda data: _get_rate_value(data, "yearly", "OTHER", "consumption"),
            "Rate Breakdown - This Year",
        ),
        OVOEnergyAUSensor(
            coordinator,
            "yearly_other_cost",
            "Other Rates Cost",
            "AUD",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
            "mdi:currency-usd",
            lambda data: _get_rate_value(data, "yearly", "OTHER", "charge"),
            "Rate Breakdown - This Year",
        ),
    ])

    # Add diagnostic sensor for plan information
    sensors.append(
        OVOEnergyAUPlanSensor(
            coordinator,
            "plan_information",
            "Plan Information",
        )
    )

    async_add_entities(sensors)


class OVOEnergyAUSensor(CoordinatorEntity, SensorEntity):
    """Representation of an OVO Energy Australia sensor."""

    def __init__(
        self,
        coordinator,
        sensor_key: str,
        sensor_name: str,
        unit: str,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        icon: str,
        value_fn,
        device_category: str = "General",
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._sensor_name = sensor_name
        self._unit = unit
        self._device_class = device_class
        self._state_class = state_class
        self._icon = icon
        self._value_fn = value_fn
        self._device_category = device_category

        # Generate unique ID
        self._attr_unique_id = f"{coordinator.account_id}_{sensor_key}"
        self._attr_has_entity_name = True

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._sensor_name

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            _LOGGER.debug("Sensor %s: coordinator.data is None", self._sensor_key)
            return None

        try:
            value = self._value_fn(self.coordinator.data)
            if value is None:
                _LOGGER.debug("Sensor %s: value_fn returned None", self._sensor_key)
                return None

            # Round to 2 decimal places
            rounded = round(float(value), 2)
            return rounded
        except Exception as err:
            _LOGGER.error(
                "Sensor %s: Error getting value: %s (data keys: %s)",
                self._sensor_key,
                err,
                list(self.coordinator.data.keys()) if self.coordinator.data else "None"
            )
            return None

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class."""
        return self._device_class

    @property
    def state_class(self) -> SensorStateClass | None:
        """Return the state class."""
        return self._state_class

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        if not self.coordinator.data:
            return {}

        attributes = {}

        # Add hourly entries for hourly sensors
        if "hourly_" in self._sensor_key:
            hourly_data = self.coordinator.data.get("hourly", {})

            if "solar" in self._sensor_key:
                entries = hourly_data.get("solar_entries", [])
                if entries:
                    attributes["entries"] = entries
                    attributes["entry_count"] = len(entries)
            elif "grid" in self._sensor_key:
                entries = hourly_data.get("grid_entries", [])
                if entries:
                    attributes["entries"] = entries
                    attributes["entry_count"] = len(entries)
            elif "return_to_grid" in self._sensor_key:
                entries = hourly_data.get("return_to_grid_entries", [])
                if entries:
                    attributes["entries"] = entries
                    attributes["entry_count"] = len(entries)

        # Add latest entry for daily/monthly/yearly sensors
        period = None
        if "daily_" in self._sensor_key:
            period = "daily"
        elif "monthly_" in self._sensor_key:
            period = "monthly"
        elif "yearly_" in self._sensor_key:
            period = "yearly"

        if period:
            period_data = self.coordinator.data.get(period, {})
            if "solar" in self._sensor_key and "solar_latest" in period_data:
                attributes["latest_entry"] = period_data["solar_latest"]
            elif ("grid" in self._sensor_key or "return" in self._sensor_key) and "grid_latest" in period_data:
                attributes["latest_entry"] = period_data["grid_latest"]

            # Add daily breakdown for monthly sensors
            if period == "monthly":
                # Solar consumption/charge daily breakdown
                if "solar" in self._sensor_key and "solar_daily_breakdown" in period_data:
                    breakdown = period_data["solar_daily_breakdown"]
                    attributes["daily_breakdown"] = breakdown
                    attributes["days_in_month"] = len(breakdown)

                    # Add statistics if available
                    if "solar_daily_avg" in period_data:
                        attributes["daily_average"] = period_data["solar_daily_avg"]
                    if "solar_daily_max" in period_data:
                        attributes["daily_max"] = period_data["solar_daily_max"]
                    if "solar_charge_daily_avg" in period_data:
                        attributes["daily_charge_average"] = period_data["solar_charge_daily_avg"]

                # Grid consumption/charge daily breakdown
                elif "grid" in self._sensor_key and "grid_daily_breakdown" in period_data:
                    breakdown = period_data["grid_daily_breakdown"]
                    attributes["daily_breakdown"] = breakdown
                    attributes["days_in_month"] = len(breakdown)

                # Return to grid daily breakdown
                elif "return" in self._sensor_key and "return_daily_breakdown" in period_data:
                    breakdown = period_data["return_daily_breakdown"]
                    attributes["daily_breakdown"] = breakdown
                    attributes["days_in_month"] = len(breakdown)

                # Rate breakdown daily attributes for monthly rate sensors
                elif period == "monthly" and any(rate_type in self._sensor_key for rate_type in ["ev_offpeak", "free_3", "other"]):
                    if "rate_daily_breakdown" in period_data:
                        breakdown = period_data["rate_daily_breakdown"]
                        attributes["rate_daily_breakdown"] = breakdown
                        attributes["days_in_month"] = len(breakdown)

        # ====================
        # ADVANCED ANALYTICS ATTRIBUTES
        # ====================

        # Feature 1: Peak Usage Time Blocks
        if self._sensor_key == "peak_4hour_consumption":
            peak_data = self.coordinator.data.get("hourly", {}).get("peak_4hour_window", {})
            if peak_data:
                attributes.update({
                    "start_time": peak_data.get("start_time"),
                    "end_time": peak_data.get("end_time"),
                    "start_hour": peak_data.get("start_hour"),
                    "hourly_breakdown": peak_data.get("hourly_breakdown", []),
                })

        # Feature 2: Week-over-Week Comparison
        if "week_comparison" in self._sensor_key:
            week_data = self.coordinator.data.get("week_comparison", {})
            if week_data:
                attributes.update({
                    "this_week": week_data.get(f"this_week_{self._sensor_key.split('_')[-1] if '_' in self._sensor_key else 'cost'}"),
                    "last_week": week_data.get(f"last_week_{self._sensor_key.split('_')[-1] if '_' in self._sensor_key else 'cost'}"),
                    "change": week_data.get(f"{self._sensor_key.split('_')[-1] if '_' in self._sensor_key else 'cost'}_change"),
                    "change_pct": week_data.get(f"{self._sensor_key.split('_')[-1] if '_' in self._sensor_key else 'cost'}_change_pct"),
                    "all_metrics": week_data,
                })

        # Feature 3: Weekday vs Weekend
        if "weekday_avg" in self._sensor_key:
            weekday_data = self.coordinator.data.get("weekday_analysis", {})
            if weekday_data:
                attributes.update(weekday_data)

        if "weekend_avg" in self._sensor_key:
            weekend_data = self.coordinator.data.get("weekend_analysis", {})
            if weekend_data:
                attributes.update(weekend_data)

        # Feature 4: Time of Use
        if "tou_" in self._sensor_key:
            tou_data = self.coordinator.data.get("hourly", {}).get("time_of_use", {})
            if tou_data:
                attributes["all_periods"] = tou_data

        # Super Off-Peak Tracking (Free 3 & EV Plans - 11am-2pm)
        if "super_off_peak" in self._sensor_key:
            free_data = self.coordinator.data.get("hourly", {}).get("free_usage", {})
            if free_data:
                attributes.update({
                    "consumption": free_data.get("consumption"),
                    "cost_saved": free_data.get("cost_saved"),
                    "hours": free_data.get("hours"),
                    "period": "11:00-14:00 daily (Super Off-Peak)",
                })

        # EV Off-Peak Tracking (00:00-06:00 daily)
        if "ev_off_peak" in self._sensor_key:
            # Determine which period based on sensor key
            if "weekly" in self._sensor_key:
                ev_data = self.coordinator.data.get("hourly", {}).get("ev_usage_weekly", {})
                period_label = "Last 7 days, 00:00-06:00 daily (EV Off-Peak)"
            elif "monthly" in self._sensor_key:
                ev_data = self.coordinator.data.get("hourly", {}).get("ev_usage_monthly", {})
                period_label = "Month to date, 00:00-06:00 daily (EV Off-Peak)"
            elif "yearly" in self._sensor_key:
                ev_data = self.coordinator.data.get("hourly", {}).get("ev_usage_yearly", {})
                period_label = "Year to date, 00:00-06:00 daily (EV Off-Peak)"
            else:
                # Default (backward compatibility)
                ev_data = self.coordinator.data.get("hourly", {}).get("ev_usage", {})
                period_label = "Month to date, 00:00-06:00 daily (EV Off-Peak)"

            if ev_data:
                attributes.update({
                    "consumption": ev_data.get("consumption"),
                    "cost": ev_data.get("cost"),
                    "cost_saved": ev_data.get("cost_saved"),
                    "hours": ev_data.get("hours"),
                    "period": period_label,
                })

        # Feature 5: Solar Self-Sufficiency
        if self._sensor_key == "self_sufficiency_score":
            sufficiency_data = self.coordinator.data.get("self_sufficiency", {})
            if sufficiency_data:
                attributes.update({
                    "solar_kwh": sufficiency_data.get("solar_kwh"),
                    "grid_kwh": sufficiency_data.get("grid_kwh"),
                    "total_kwh": sufficiency_data.get("total_kwh"),
                    "period_days": sufficiency_data.get("period_days"),
                })

        # Feature 6: High Usage Days
        if self._sensor_key == "high_usage_days":
            high_usage = self.coordinator.data.get("high_usage_days", [])
            if high_usage:
                attributes["rankings"] = high_usage
                attributes["rank_count"] = len(high_usage)

        # Feature 7: Hourly Heatmap
        if self._sensor_key == "hourly_heatmap":
            heatmap = self.coordinator.data.get("hourly", {}).get("hourly_heatmap", {})
            if heatmap:
                attributes["heatmap_data"] = heatmap
                attributes["days_available"] = list(heatmap.keys())

        # Feature 8: Cost Per kWh
        if "cost_per_kwh" in self._sensor_key:
            cost_data = self.coordinator.data.get("cost_per_kwh", {})
            if cost_data:
                attributes.update({
                    "overall_rate": cost_data.get("overall"),
                    "grid_rate": cost_data.get("grid"),
                    "solar_rate": cost_data.get("solar"),
                    "total_cost": cost_data.get("total_cost"),
                    "total_consumption": cost_data.get("total_consumption"),
                })

        # Feature 9: Monthly Projection
        if "monthly_projection" in self._sensor_key or "monthly_daily_average" in self._sensor_key:
            projection_data = self.coordinator.data.get("monthly_projection", {})
            if projection_data:
                attributes.update({
                    "projected_total": projection_data.get("projected_total"),
                    "current_mtd": projection_data.get("current_mtd"),
                    "projected_remaining": projection_data.get("projected_remaining"),
                    "daily_average": projection_data.get("daily_average"),
                    "days_elapsed": projection_data.get("days_elapsed"),
                    "days_remaining": projection_data.get("days_remaining"),
                    "days_in_month": projection_data.get("days_in_month"),
                })

        # Feature 10: Return-to-Grid Value
        if "rtg_" in self._sensor_key:
            rtg_data = self.coordinator.data.get("return_to_grid_analysis", {})
            if rtg_data:
                attributes.update({
                    "export_kwh": rtg_data.get("export_kwh"),
                    "export_credit": rtg_data.get("export_credit"),
                    "export_rate": rtg_data.get("export_rate_per_kwh"),
                    "purchase_rate": rtg_data.get("purchase_rate_per_kwh"),
                    "rate_difference": rtg_data.get("rate_difference"),
                    "potential_savings": rtg_data.get("potential_savings"),
                    "opportunity_cost": rtg_data.get("opportunity_cost"),
                })

        return attributes

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, f"{self.coordinator.account_id}_{self._device_category}")},
            "name": f"OVO Energy AU - {self._device_category}",
            "manufacturer": "OVO Energy Australia",
            "model": "Energy Monitor",
            "via_device": (DOMAIN, self.coordinator.account_id),
        }


class OVOEnergyAUDaySensor(CoordinatorEntity, SensorEntity):
    """Representation of a dynamic day sensor (last 3 days)."""

    def __init__(
        self,
        coordinator,
        sensor_key: str,
        sensor_name: str,
        unit: str,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        icon: str,
        day_index: int,
        value_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._sensor_name = sensor_name
        self._unit = unit
        self._device_class = device_class
        self._state_class = state_class
        self._icon = icon
        self._day_index = day_index
        self._value_key = value_key

        # Generate unique ID
        self._attr_unique_id = f"{coordinator.account_id}_{sensor_key}"
        self._attr_has_entity_name = True

    @property
    def name(self) -> str:
        """Return the name with day and date."""
        if not self.coordinator.data:
            return self._sensor_name

        last_3_days = self.coordinator.data.get("last_3_days", [])
        if self._day_index < len(last_3_days):
            day_data = last_3_days[self._day_index]
            day_name = day_data.get("day_name", "")
            date = day_data.get("date", "")
            # Format: "Monday 20 Jan" for example
            date_formatted = ""
            if date:
                try:
                    from datetime import datetime
                    dt = datetime.strptime(date, "%Y-%m-%d")
                    date_formatted = dt.strftime("%d %b")
                except:
                    date_formatted = date

            if day_name and date_formatted:
                return f"{day_name} {date_formatted}"

        return self._sensor_name

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        last_3_days = self.coordinator.data.get("last_3_days", [])
        if self._day_index < len(last_3_days):
            day_data = last_3_days[self._day_index]
            value = day_data.get(self._value_key, 0)
            return round(float(value), 2) if value is not None else 0

        return None

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class."""
        return self._device_class

    @property
    def state_class(self) -> SensorStateClass | None:
        """Return the state class."""
        return self._state_class

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        if not self.coordinator.data:
            return {}

        last_3_days = self.coordinator.data.get("last_3_days", [])
        if self._day_index < len(last_3_days):
            day_data = last_3_days[self._day_index]
            return {
                "date": day_data.get("date"),
                "day_name": day_data.get("day_name"),
                "day": day_data.get("day"),
                "month": day_data.get("month"),
                "year": day_data.get("year"),
            }

        return {}

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, f"{self.coordinator.account_id}_3 Day Snapshot")},
            "name": "OVO Energy AU - 3 Day Snapshot",
            "manufacturer": "OVO Energy Australia",
            "model": "Energy Monitor",
            "via_device": (DOMAIN, self.coordinator.account_id),
        }


class OVOEnergyAUPlanSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic sensor displaying plan information from OVO API."""

    def __init__(
        self,
        coordinator,
        sensor_key: str,
        sensor_name: str,
    ) -> None:
        """Initialize the plan sensor."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._sensor_name = sensor_name

        # Generate unique ID
        self._attr_unique_id = f"{coordinator.account_id}_{sensor_key}"
        self._attr_has_entity_name = True

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._sensor_name

    @property
    def native_value(self) -> str | None:
        """Return the plan name as the sensor state."""
        if not self.coordinator.data:
            _LOGGER.debug("Plan sensor: No coordinator data")
            return None

        product_agreements = self.coordinator.data.get("product_agreements")
        if not product_agreements or not isinstance(product_agreements, dict):
            _LOGGER.debug("Plan sensor: No valid product_agreements in coordinator data (got: %s)", type(product_agreements).__name__ if product_agreements else "None")
            return "Unknown"

        _LOGGER.debug("Plan sensor: product_agreements keys: %s", list(product_agreements.keys()))

        agreements = product_agreements.get("productAgreements", [])
        if not agreements:
            _LOGGER.warning("Plan sensor: No productAgreements found in data")
            return "No Plan"

        # Get the first active product agreement
        agreement = agreements[0]
        product = agreement.get("product", {})
        plan_name = product.get("displayName", "Unknown Plan")

        _LOGGER.debug("Plan sensor: Displaying plan name: %s", plan_name)
        return plan_name

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:file-document-outline"

    @property
    def entity_category(self) -> EntityCategory:
        """Return the entity category."""
        return EntityCategory.DIAGNOSTIC

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return plan details as attributes for sidebar display."""
        if not self.coordinator.data:
            return {}

        product_agreements = self.coordinator.data.get("product_agreements")
        if not product_agreements:
            return {"status": "No plan data available"}

        agreements = product_agreements.get("productAgreements", [])
        if not agreements:
            return {"status": "No product agreements found"}

        # Get the first active product agreement
        agreement = agreements[0]
        product = agreement.get("product", {})
        unit_rates = product.get("unitRatesCentsPerKWH", {})

        attributes = {
            "account_id": product_agreements.get("id", "Unknown"),
            "plan_name": product.get("displayName", "Unknown"),
            "product_code": product.get("code", "Unknown"),
            "nmi": agreement.get("nmi", "Unknown"),
            "agreement_id": agreement.get("id", "Unknown"),
            "from_date": agreement.get("fromDt", "Unknown"),
            "to_date": agreement.get("toDt", "Unknown"),
        }

        # Standing charge
        standing_charge_cents = product.get("standingChargeCentsPerDay", 0)
        if standing_charge_cents:
            attributes["standing_charge_cents_per_day"] = standing_charge_cents
            attributes["standing_charge_aud_per_day"] = round(standing_charge_cents / 100, 2)

        # Unit rates (convert from cents/kWh to $/kWh for display)
        rates = {}
        if unit_rates.get("peak") is not None:
            rates["peak_cents_kwh"] = unit_rates["peak"]
            rates["peak_aud_kwh"] = round(unit_rates["peak"] / 100, 4)
        if unit_rates.get("shoulder") is not None:
            rates["shoulder_cents_kwh"] = unit_rates["shoulder"]
            rates["shoulder_aud_kwh"] = round(unit_rates["shoulder"] / 100, 4)
        if unit_rates.get("offPeak") is not None:
            rates["off_peak_cents_kwh"] = unit_rates["offPeak"]
            rates["off_peak_aud_kwh"] = round(unit_rates["offPeak"] / 100, 4)
        if unit_rates.get("evOffPeak") is not None:
            rates["ev_off_peak_cents_kwh"] = unit_rates["evOffPeak"]
            rates["ev_off_peak_aud_kwh"] = round(unit_rates["evOffPeak"] / 100, 4)
        if unit_rates.get("superOffPeak") is not None:
            rates["super_off_peak_cents_kwh"] = unit_rates["superOffPeak"]
            rates["super_off_peak_aud_kwh"] = round(unit_rates["superOffPeak"] / 100, 4)
        if unit_rates.get("standard") is not None:
            rates["standard_cents_kwh"] = unit_rates["standard"]
            rates["standard_aud_kwh"] = round(unit_rates["standard"] / 100, 4)
        if unit_rates.get("feedInTariff") is not None:
            rates["feed_in_tariff_cents_kwh"] = unit_rates["feedInTariff"]
            rates["feed_in_tariff_aud_kwh"] = round(unit_rates["feedInTariff"] / 100, 4)
        if unit_rates.get("CL1") is not None:
            rates["cl1_cents_kwh"] = unit_rates["CL1"]
        if unit_rates.get("CL2") is not None:
            rates["cl2_cents_kwh"] = unit_rates["CL2"]

        # Add all rates to attributes
        attributes.update(rates)

        return attributes

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.account_id)},
            "name": "OVO Energy AU",
            "manufacturer": "OVO Energy Australia",
            "model": "Energy Monitor",
        }
