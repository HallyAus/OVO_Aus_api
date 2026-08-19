"""Read-only Kaluza vehicle API support for OVO Energy Australia.

The MyOVO EV dashboard uses a short-lived Firebase/Kaluza token obtained from
the authenticated OVO account.  This module mirrors the dashboard's GET-only
requests and deliberately removes identifiers and location data before the
result reaches Home Assistant.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import aiohttp

from .const import API_BASE_URL, AU_TIMEZONE

FLEX_API_BASE_URL = "https://d2v.api.aus-se1.flex.kaluza.com"
FIRESTORE_BASE_URL = (
    "https://firestore.googleapis.com/v1/projects/"
    "flex-aus-se1-firebase-prod/databases/(default)/documents"
)

RateLimiter = Callable[[], Awaitable[None]]


class OVOVehicleApiError(Exception):
    """Base error for the optional vehicle data source."""


class OVOVehicleAuthenticationError(OVOVehicleApiError):
    """The short-lived Kaluza/Firebase token was rejected."""


class OVOVehicleCommunicationError(OVOVehicleApiError):
    """A vehicle endpoint could not be reached or decoded."""


def decode_firestore_value(value: dict[str, Any] | None) -> Any:
    """Decode one Firestore REST value into ordinary Python data."""
    if not isinstance(value, dict):
        return None
    if "nullValue" in value:
        return None
    if "booleanValue" in value:
        return bool(value["booleanValue"])
    if "integerValue" in value:
        try:
            return int(value["integerValue"])
        except (TypeError, ValueError):
            return None
    if "doubleValue" in value:
        try:
            return float(value["doubleValue"])
        except (TypeError, ValueError):
            return None
    for key in ("stringValue", "timestampValue"):
        if key in value:
            return value[key]
    if "arrayValue" in value:
        values = (value.get("arrayValue") or {}).get("values") or []
        return [decode_firestore_value(item) for item in values]
    if "mapValue" in value:
        fields = (value.get("mapValue") or {}).get("fields") or {}
        return {key: decode_firestore_value(item) for key, item in fields.items()}
    return None


def decode_firestore_documents(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Decode Firestore documents while retaining IDs only for local matching."""
    documents: list[dict[str, Any]] = []
    for document in (payload or {}).get("documents") or []:
        if not isinstance(document, dict):
            continue
        fields = {
            key: decode_firestore_value(value)
            for key, value in (document.get("fields") or {}).items()
        }
        name = document.get("name")
        fields["_document_id"] = name.rsplit("/", 1)[-1] if isinstance(name, str) else ""
        documents.append(fields)
    return documents


def _epoch_to_iso(value: Any) -> str | None:
    """Convert a seconds-or-milliseconds epoch to a UTC ISO timestamp."""
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    if timestamp > 10_000_000_000:
        timestamp /= 1000
    try:
        return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _device_hash(account_id: str, device_id: str) -> str:
    """Return a stable opaque entity identifier, never the Kaluza device ID."""
    return hashlib.sha256(f"{account_id}:{device_id}".encode()).hexdigest()[:16]


def _normalise_cost(cost: Any) -> float | None:
    if isinstance(cost, dict):
        cost = cost.get("value")
    try:
        return round(float(cost), 2)
    except (TypeError, ValueError):
        return None


def _normalise_energy_block(block: Any) -> dict[str, Any]:
    """Keep the useful, non-identifying portion of a KAPI energy block."""
    if not isinstance(block, dict):
        return {}
    imported = (((block.get("totals") or {}).get("total") or {}).get("imported") or {})
    rates = []
    for item in imported.get("rates") or []:
        if not isinstance(item, dict):
            continue
        rate = item.get("rate") or {}
        rates.append(
            {
                "timing_category": rate.get("timingCategory"),
                "kwh": item.get("kwh"),
                "cost_aud": _normalise_cost(item.get("cost")),
            }
        )
    source_mix = []
    for item in imported.get("energySourceMix") or []:
        if isinstance(item, dict):
            source_mix.append({"source": item.get("source"), "kwh": item.get("kwh")})
    return {
        "inclusive_start": block.get("inclusiveStartDate"),
        "exclusive_end": block.get("exclusiveEndDate"),
        "granularity": block.get("granularity"),
        "kwh": imported.get("kwh"),
        "cost_aud": _normalise_cost(imported.get("cost")),
        "rates": rates,
        "energy_source_mix": source_mix,
    }


def _normalise_monthly_energy(document: dict[str, Any] | None) -> dict[str, Any]:
    if not document:
        return {}
    result = _normalise_energy_block(document)
    result["periods"] = [
        _normalise_energy_block(period)
        for period in document.get("periods") or []
        if isinstance(period, dict)
    ]
    return result


def _safe_charge_plan(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    intervals = []
    for interval in payload.get("chargePlan") or []:
        if not isinstance(interval, dict):
            continue
        intervals.append(
            {
                "start": interval.get("startTimeInclusive"),
                "end": interval.get("endTimeExclusive"),
                "should_charge": interval.get("shouldCharge"),
                "charge_limit_percent": interval.get("chargeLimitPercent"),
                "predicted_final_battery_percent": interval.get(
                    "predictedFinalBatteryPercent"
                ),
                "reason": interval.get("reason"),
            }
        )
    return {"updated_at": payload.get("updatedAt"), "intervals": intervals}


def _safe_charging_times(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    periods = []
    for period in payload.get("tariffRateChargingPeriods") or []:
        if isinstance(period, dict):
            periods.append(
                {
                    "timing_category": period.get("timingCategory"),
                    "advanced_charge_limit_percent": period.get(
                        "advancedChargeLimitPercent"
                    ),
                    "selected_in_basic": period.get("isSelectedInBasic"),
                }
            )
    return {
        "mode": payload.get("chargingTimesMode"),
        "demand_period_charging_enabled": payload.get(
            "demandPeriodChargingEnabled"
        ),
        "tariff_configured": bool(payload.get("tariffID")),
        "periods": periods,
    }


def _safe_preferences(preferences: dict[str, Any] | None) -> dict[str, Any]:
    preferences = preferences or {}
    weekdays = {
        day: preferences.get(day)
        for day in (
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        )
        if preferences.get(day) is not None
    }
    tariff_periods = []
    for period in preferences.get("tariffPeriods") or []:
        if isinstance(period, dict):
            tariff_periods.append(
                {
                    "start": period.get("timeStart"),
                    "end": period.get("timeEnd"),
                    "rate": period.get("ratePence"),
                }
            )
    return {
        "maximum_charge_power_w": preferences.get("assetMaxRateOfChargeWatts"),
        "minimum_charge_power_w": preferences.get("assetMinRateOfChargeWatts"),
        "battery_capacity_wh": preferences.get("batteryCapacityWh"),
        "minimum_soc_percent": preferences.get("minBatterySocPercent"),
        "maximum_soc_percent": preferences.get("maxBatterySocPercent"),
        "optimisation_type": preferences.get("optimisationType"),
        "energy_supplier": preferences.get("energySupplierName"),
        "tariff": preferences.get("tariff"),
        "weekdays": weekdays,
        "tariff_periods": tariff_periods,
        "updated_at": _epoch_to_iso(preferences.get("ts")),
    }


def build_vehicle_data(
    account_id: str,
    registrations: list[dict[str, Any]],
    vehicle_documents: list[dict[str, Any]],
    energy_documents: list[dict[str, Any]],
    charge_plans: dict[str, dict[str, Any]],
    charging_times: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build the privacy-filtered vehicle data returned to Home Assistant."""
    registrations_by_device = {
        str(item.get("virtualDeviceId")): item
        for item in registrations
        if item.get("virtualDeviceId")
    }
    vehicles_by_device = {
        str(item.get("_document_id")): item
        for item in vehicle_documents
        if item.get("_document_id")
    }
    # A registration can arrive before the vehicle telemetry document.
    for device_id in registrations_by_device:
        vehicles_by_device.setdefault(device_id, {})

    energy_by_device = {
        str(item.get("_document_id")): item
        for item in energy_documents
        if item.get("_document_id")
    }
    # Some accounts return one monthly document without a device-matching ID.
    # Use that fallback only when there is also exactly one vehicle; otherwise
    # it would duplicate one vehicle's energy across a multi-vehicle account.
    single_energy = (
        energy_documents[0]
        if len(energy_documents) == 1 and len(vehicles_by_device) == 1
        else None
    )

    result = []
    for device_id, vehicle in vehicles_by_device.items():
        registration = registrations_by_device.get(device_id, {})
        telemetry = vehicle.get("latestTelemetry") or {}
        vendor_tesla = ((vehicle.get("vendorSpecific") or {}).get("tesla") or {})
        make = vehicle.get("vehicleMake") or registration.get("vehicleMake")
        model = vehicle.get("vehicleModel") or registration.get("vehicleModel")
        energy = energy_by_device.get(device_id) or single_energy

        # VIN, latitude/longitude, home-presence flags, account/user/device IDs,
        # optimisation signal IDs, and certificate-install URLs are intentionally
        # never copied into this returned structure.
        result.append(
            {
                "id": _device_hash(account_id, device_id),
                "name": " ".join(str(value) for value in (make, model) if value)
                or "Electric Vehicle",
                "make": make,
                "model": model,
                "status": (
                    "Deauthorised"
                    if vehicle.get("hasInvalidCredentials") is True
                    else "Registered"
                ),
                "control_ready": registration.get("controlReady"),
                "integration": registration.get("integration"),
                "timezone": registration.get("timeZoneName"),
                "battery_soc_percent": telemetry.get("batterySocPercent"),
                "estimated_range_km": telemetry.get("estimatedRangeKm"),
                "cable_state": telemetry.get("cableState"),
                "charge_limit_percent": telemetry.get("chargeLimit"),
                "mode": telemetry.get("mode"),
                "is_boosting": telemetry.get("isBoosting"),
                "battery_capacity_kwh": (
                    round(float(telemetry["batteryCapacityWattHours"]) / 1000, 2)
                    if telemetry.get("batteryCapacityWattHours") is not None
                    else None
                ),
                "telemetry_updated_at": _epoch_to_iso(telemetry.get("ts")),
                "estimated_charge_start": _epoch_to_iso(
                    vehicle.get("estimatedChargeStartTime")
                ),
                "vehicle_updated_at": _epoch_to_iso(vehicle.get("ts")),
                "certificate_installed": vendor_tesla.get("isCertificateInstalled"),
                "preferences": _safe_preferences(vehicle.get("chargingPreferences")),
                "charge_plan": _safe_charge_plan(charge_plans.get(device_id)),
                "charging_times": _safe_charging_times(charging_times.get(device_id)),
                "monthly_energy": _normalise_monthly_energy(energy),
            }
        )
    return result


class OVOVehicleApiClient:
    """GET-only client for the Kaluza vehicle endpoints used by MyOVO."""

    def __init__(self, session: aiohttp.ClientSession, rate_limiter: RateLimiter) -> None:
        self._session = session
        self._rate_limiter = rate_limiter
        self._token_cache: dict[str, tuple[str, str, datetime]] = {}

    async def _get_json(
        self, url: str, bearer_token: str, *, optional: bool = False
    ) -> dict[str, Any]:
        await self._rate_limiter()
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {bearer_token}",
            "origin": API_BASE_URL,
            "referer": f"{API_BASE_URL}/EV",
        }
        try:
            async with self._session.get(url, headers=headers) as response:
                if response.status in (401, 403):
                    raise OVOVehicleAuthenticationError(
                        "Vehicle data authorization was rejected"
                    )
                if response.status == 404 and optional:
                    return {}
                response.raise_for_status()
                data = await response.json()
                return data if isinstance(data, dict) else {}
        except OVOVehicleApiError:
            raise
        except (aiohttp.ClientError, ValueError, TypeError) as err:
            raise OVOVehicleCommunicationError(
                "Could not retrieve vehicle data"
            ) from err

    async def _get_flex_token(
        self, account_id: str, myovo_access_token: str, *, force: bool = False
    ) -> tuple[str, str]:
        cached = self._token_cache.get(account_id)
        if not force and cached and datetime.now(UTC) < cached[2]:
            return cached[0], cached[1]

        account = quote(str(account_id), safe="")
        payload = await self._get_json(
            f"{FLEX_API_BASE_URL}/v1.0/api/account/{account}/token",
            myovo_access_token,
        )
        token = payload.get("idToken")
        user_id = payload.get("userId")
        if not isinstance(token, str) or not isinstance(user_id, str):
            raise OVOVehicleCommunicationError(
                "Vehicle authorization response was incomplete"
            )
        try:
            lifetime = max(60, int(payload.get("expiresIn", 900)))
        except (TypeError, ValueError):
            lifetime = 900
        expires = datetime.now(UTC) + timedelta(seconds=max(30, lifetime - 60))
        self._token_cache[account_id] = (token, user_id, expires)
        return token, user_id

    async def _fetch_with_token(
        self, account_id: str, myovo_access_token: str, *, force: bool = False
    ) -> list[dict[str, Any]]:
        token, user_id = await self._get_flex_token(
            account_id, myovo_access_token, force=force
        )
        user = quote(user_id, safe="")
        root = f"{FIRESTORE_BASE_URL}/users/{user}"
        registration_raw = await self._get_json(
            f"{root}/registration", token, optional=True
        )
        vehicles_raw = await self._get_json(f"{root}/vehicles", token, optional=True)
        month = datetime.now(AU_TIMEZONE).strftime("%Y-%m")
        energy_raw = await self._get_json(
            f"{root}/energy_consumption_monthly_kapi/{month}/devices",
            token,
            optional=True,
        )

        registrations = decode_firestore_documents(registration_raw)
        vehicles = decode_firestore_documents(vehicles_raw)
        energy = decode_firestore_documents(energy_raw)
        device_ids = {
            str(item.get("_document_id"))
            for item in vehicles
            if item.get("_document_id")
        } | {
            str(item.get("virtualDeviceId"))
            for item in registrations
            if item.get("virtualDeviceId")
        }

        plans: dict[str, dict[str, Any]] = {}
        times: dict[str, dict[str, Any]] = {}
        for device_id in sorted(device_ids):
            device = quote(device_id, safe="")
            plans[device_id] = await self._get_json(
                f"{FLEX_API_BASE_URL}/v1/users/{user}/devices/{device}/charge-plan",
                token,
                optional=True,
            )
            times[device_id] = await self._get_json(
                f"{FLEX_API_BASE_URL}/v2/users/{user}/devices/{device}/charging-times",
                token,
                optional=True,
            )

        return build_vehicle_data(
            account_id, registrations, vehicles, energy, plans, times
        )

    async def async_get_vehicle_data(
        self, account_id: str, myovo_access_token: str
    ) -> list[dict[str, Any]]:
        """Return all privacy-filtered vehicle data, refreshing once on 401."""
        try:
            return await self._fetch_with_token(account_id, myovo_access_token)
        except OVOVehicleAuthenticationError:
            self._token_cache.pop(account_id, None)
            try:
                return await self._fetch_with_token(
                    account_id, myovo_access_token, force=True
                )
            except OVOVehicleAuthenticationError as err:
                raise OVOVehicleCommunicationError(
                    "Vehicle data authorization is unavailable"
                ) from err
