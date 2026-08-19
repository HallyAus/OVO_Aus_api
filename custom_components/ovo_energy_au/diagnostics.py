"""Privacy-safe diagnostics for OVO Energy Australia."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_ACCOUNT_ID

_TO_REDACT = {
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_ACCOUNT_ID,
    "username",
    "password",
    "account_id",
    "unique_id",
    "title",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics without bills, meter IDs, addresses, or tokens."""
    coordinator = entry.runtime_data
    data = coordinator.data or {}
    hourly = data.get("hourly") or {}
    agreements = (data.get("product_agreements") or {}).get("productAgreements") or []
    product = (agreements[0].get("product") or {}) if agreements else {}
    vehicles = data.get("vehicles") or []

    last_success = getattr(coordinator, "last_update_success_time", None)
    return {
        "config_entry": async_redact_data(entry.as_dict(), _TO_REDACT),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_successful_update": (
                last_success.isoformat() if last_success is not None else None
            ),
            "plan_type": coordinator.plan_config.plan_type,
            "plan_name": product.get("displayName"),
            "has_solar": data.get("has_solar"),
            "meter_type": data.get("meter_type"),
            "api_timezone": data.get("api_timezone"),
            "daily_entries": len(data.get("all_daily_entries") or []),
            "hourly_solar_entries": len(hourly.get("solar_entries") or []),
            "hourly_grid_entries": len(hourly.get("grid_entries") or []),
            "hourly_export_entries": len(
                hourly.get("return_to_grid_entries") or []
            ),
            "statements_available": len(data.get("statements") or []),
            "payments_available": len(data.get("payments") or []),
            "billing_overview_available": bool(data.get("billing_information")),
            "unbilled_charges_available": bool(data.get("unbilled_charges")),
            "vehicles_available": len(vehicles),
            "vehicle_telemetry_available": sum(
                1 for vehicle in vehicles if vehicle.get("telemetry_updated_at")
            ),
            "vehicle_charge_plans_available": sum(
                1
                for vehicle in vehicles
                if (vehicle.get("charge_plan") or {}).get("intervals")
            ),
            "vehicle_monthly_energy_available": sum(
                1
                for vehicle in vehicles
                if (vehicle.get("monthly_energy") or {}).get("kwh") is not None
            ),
        },
    }
