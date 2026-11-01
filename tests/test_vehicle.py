"""Kaluza vehicle decoding, privacy, and sensor regression tests."""

import traceback
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlparse

import aiohttp
import jwt
import pytest

from custom_components.ovo_energy_au.sensors.vehicle import (
    VEHICLE_SENSOR_DEFINITIONS,
    OVOVehicleChargePlanSensor,
    OVOVehicleMetricSensor,
    OVOVehiclePreferencesSensor,
    OVOVehicleScheduleSensor,
    OVOVehicleStatusSensor,
    create_vehicle_sensors,
)
from custom_components.ovo_energy_au.vehicle import (
    OVOVehicleApiClient,
    OVOVehicleCommunicationError,
    build_vehicle_data,
    decode_firestore_documents,
    decode_firestore_value,
)


class _FakeResponse:
    def __init__(self, payload, status=200, url="https://example.test"):
        self._payload = payload
        self.status = status
        self.url = url

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def raise_for_status(self):
        return None

    async def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, *, reject_refresh=False):
        self.calls = []
        self.kaluza_nonce = None
        self.reject_refresh = reject_refresh

    def get(self, url, headers=None, **kwargs):
        self.calls.append(("GET", url, headers or {}, kwargs))
        if "/authorize?" in url:
            query = parse_qs(urlparse(url).query)
            self.kaluza_nonce = query["nonce"][0]
            callback = (
                "https://my.ovoenergy.com.au?login=kapi"
                f"&code=kaluza-code&state={query['state'][0]}"
            )
            return _FakeResponse({}, url=callback)
        if url.endswith("/token"):
            return _FakeResponse(
                {"idToken": "flex-token", "userId": "user-id", "expiresIn": 900}
            )
        return _FakeResponse({})

    def post(self, url, json, **kwargs):
        self.calls.append(("POST", url, {}, {"json": json, **kwargs}))
        if json["grant_type"] == "refresh_token":
            if self.reject_refresh:
                return _FakeResponse({}, status=401)
            return _FakeResponse(
                {
                    "access_token": "refreshed-kaluza-token",
                    "refresh_token": "rotated-refresh-token",
                    "expires_in": 3600,
                }
            )
        return _FakeResponse(
            {
                "access_token": "kaluza-token",
                "refresh_token": "kaluza-refresh-token",
                "expires_in": 3600,
                "id_token": jwt.encode(
                    {"nonce": self.kaluza_nonce}, key="", algorithm="none"
                ),
            }
        )


def test_firestore_decoder_handles_nested_types():
    value = {
        "mapValue": {
            "fields": {
                "number": {"integerValue": "42"},
                "decimal": {"doubleValue": 3.5},
                "enabled": {"booleanValue": True},
                "items": {
                    "arrayValue": {
                        "values": [
                            {"stringValue": "one"},
                            {"nullValue": None},
                        ]
                    }
                },
            }
        }
    }
    assert decode_firestore_value(value) == {
        "number": 42,
        "decimal": 3.5,
        "enabled": True,
        "items": ["one", None],
    }


@pytest.mark.asyncio
async def test_vehicle_client_uses_verified_get_only_token_chain_and_cache():
    session = _FakeSession()

    async def no_wait():
        return None

    client = OVOVehicleApiClient(session, no_wait)
    assert await client.async_get_vehicle_data("account", "customer") == []
    assert await client.async_get_vehicle_data("account", "customer") == []

    authorize_calls = [call for call in session.calls if "/authorize?" in call[1]]
    assert len(authorize_calls) == 1
    authorize_query = parse_qs(urlparse(authorize_calls[0][1]).query)
    assert authorize_query["account_id"] == ["account"]
    assert authorize_query["customer_id"] == ["customer"]

    token_calls = [
        call
        for call in session.calls
        if call[0] == "GET" and call[1].endswith("/token")
    ]
    assert len(token_calls) == 1
    assert token_calls[0][2]["authorization"] == "Bearer kaluza-token"
    data_calls = [
        call
        for call in session.calls
        if call[0] == "GET"
        and "/authorize?" not in call[1]
        and not call[1].endswith("/token")
    ]
    assert data_calls
    assert all(call[2]["authorization"] == "Bearer flex-token" for call in data_calls)
    assert all("/users/user-id/" in call[1] for call in data_calls)
    assert all(call[1].startswith("https://") for call in session.calls)
    assert all(
        call[3]["allow_redirects"] is False
        for call in session.calls
        if "/authorize?" not in call[1]
    )


@pytest.mark.asyncio
async def test_vehicle_client_prefers_kaluza_refresh_token_over_sso():
    session = _FakeSession()

    async def no_wait():
        return None

    client = OVOVehicleApiClient(session, no_wait)
    client._kaluza_tokens["account"] = (
        "expired-token",
        "refresh-token",
        datetime.now(UTC) - timedelta(seconds=1),
    )

    assert await client.async_get_vehicle_data("account", "customer") == []

    authorize_calls = [call for call in session.calls if "/authorize?" in call[1]]
    assert authorize_calls == []
    refresh_calls = [
        call
        for call in session.calls
        if call[0] == "POST"
        and call[3]["json"].get("grant_type") == "refresh_token"
    ]
    assert len(refresh_calls) == 1
    assert refresh_calls[0][3]["allow_redirects"] is False
    flex_call = next(
        call
        for call in session.calls
        if call[0] == "GET" and call[1].endswith("/token")
    )
    assert flex_call[2]["authorization"] == "Bearer refreshed-kaluza-token"


@pytest.mark.asyncio
async def test_vehicle_client_uses_sso_only_after_kaluza_refresh_rejection():
    session = _FakeSession(reject_refresh=True)

    async def no_wait():
        return None

    client = OVOVehicleApiClient(session, no_wait)
    client._kaluza_tokens["account"] = (
        "expired-token",
        "rejected-refresh-token",
        datetime.now(UTC) - timedelta(seconds=1),
    )

    assert await client.async_get_vehicle_data("account", "customer") == []

    grants = [
        call[3]["json"]["grant_type"]
        for call in session.calls
        if call[0] == "POST" and call[1].endswith("/oauth/token")
    ]
    assert grants == ["refresh_token", "authorization_code"]
    assert len([call for call in session.calls if "/authorize?" in call[1]]) == 1


async def _call_vehicle_endpoint(client, operation):
    if operation == "data":
        return await client._get_json("https://example.test/data", "synthetic-access")
    if operation == "exchange":
        return await client._authorize_kaluza("synthetic-account", "synthetic-customer")
    return await client._refresh_kaluza_token("synthetic-account", "synthetic-refresh")


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["data", "exchange", "refresh"])
@pytest.mark.parametrize("redirect_status", [302, 307, 308])
async def test_vehicle_endpoints_reject_redirect_responses(operation, redirect_status):
    session = _FakeSession()
    if operation == "data":
        session.get = MagicMock(return_value=_FakeResponse({}, status=redirect_status))
    else:
        session.post = MagicMock(return_value=_FakeResponse({}, status=redirect_status))
    client = OVOVehicleApiClient(session, AsyncMock())

    with pytest.raises(OVOVehicleCommunicationError, match="redirect"):
        await _call_vehicle_endpoint(client, operation)

    request = session.get if operation == "data" else session.post
    assert request.call_args.kwargs["allow_redirects"] is False
    assert client._kaluza_tokens == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["data", "exchange", "refresh"])
@pytest.mark.parametrize("error_type", [aiohttp.ClientError, TimeoutError])
async def test_vehicle_transport_errors_hide_provider_context(operation, error_type):
    session = MagicMock()
    private_context = "sensitive-vehicle-provider-context"
    session.get.side_effect = error_type(private_context)
    session.post.side_effect = error_type(private_context)
    client = OVOVehicleApiClient(session, AsyncMock())

    with pytest.raises(OVOVehicleCommunicationError) as captured:
        await _call_vehicle_endpoint(client, operation)

    assert private_context not in "".join(traceback.format_exception(captured.value))


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [None, [], "malformed"])
@pytest.mark.parametrize("optional", [False, True])
async def test_malformed_vehicle_data_is_not_treated_as_empty(payload, optional):
    session = MagicMock()
    session.get.return_value = _FakeResponse(payload)
    client = OVOVehicleApiClient(session, AsyncMock())

    with pytest.raises(OVOVehicleCommunicationError, match="Invalid vehicle API response"):
        await client._get_json("https://example.test/data", "synthetic-access", optional=optional)


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["kaluza", "flex"])
@pytest.mark.parametrize("expires_in", ["invalid", float("inf"), 10**100, -1, 0, True])
async def test_invalid_vehicle_token_lifetime_preserves_cache(source, expires_in):
    client = OVOVehicleApiClient(MagicMock(), AsyncMock())
    previous = ("synthetic-old-access", "synthetic-old-refresh", datetime.now(UTC))
    client._kaluza_tokens["account"] = previous
    client._token_cache["account"] = previous

    with pytest.raises(OVOVehicleCommunicationError):
        if source == "kaluza":
            client._store_kaluza_tokens("account", {"access_token": "synthetic-new-access", "expires_in": expires_in})
        else:
            client._get_json = AsyncMock(
                return_value={"idToken": "synthetic-new-access", "userId": "synthetic-user", "expiresIn": expires_in}
            )
            await client._get_flex_token("account", "synthetic-kaluza-access", force=True)

    assert client._kaluza_tokens["account"] == previous
    assert client._token_cache["account"] == previous


@pytest.mark.asyncio
@pytest.mark.parametrize("source,field", [("kaluza", "access_token"), ("flex", "idToken"), ("flex", "userId")])
async def test_empty_vehicle_token_fields_are_rejected(source, field):
    client = OVOVehicleApiClient(MagicMock(), AsyncMock())
    with pytest.raises(OVOVehicleCommunicationError):
        if source == "kaluza":
            client._store_kaluza_tokens("account", {field: ""})
        else:
            client._get_json = AsyncMock(return_value={"idToken": "synthetic-access", "userId": "synthetic-user", field: ""})
            await client._get_flex_token("account", "synthetic-kaluza-access")

    assert client._kaluza_tokens == {}
    assert client._token_cache == {}


def test_firestore_document_id_is_only_retained_for_local_matching():
    documents = decode_firestore_documents(
        {
            "documents": [
                {
                    "name": "projects/p/databases/d/documents/users/u/vehicles/device-raw",
                    "fields": {"vehicleMake": {"stringValue": "Example"}},
                }
            ]
        }
    )
    assert documents == [{"vehicleMake": "Example", "_document_id": "device-raw"}]


def _sample_vehicle_data():
    return build_vehicle_data(
        "account-secret",
        [
            {
                "virtualDeviceId": "device-secret",
                "controlReady": True,
                "integration": "CONNECTED_CAR",
                "timeZoneName": "Australia/Sydney",
                "optimisationSignalId": "signal-secret",
                "retailAccountNumber": "account-secret",
                "userUID": "user-secret",
            }
        ],
        [
            {
                "_document_id": "device-secret",
                "vehicleMake": "Example",
                "vehicleModel": "EV",
                "estimatedChargeStartTime": 1_787_140_800_000,
                "latestTelemetry": {
                    "batterySocPercent": 62.5,
                    "batteryCapacityWattHours": 75_000,
                    "estimatedRangeKm": 280,
                    "cableState": "CONNECTED",
                    "chargeLimit": 80,
                    "mode": "SMART",
                    "isBoosting": False,
                    "isAtHome": True,
                    "isHomeLocationSet": True,
                    "location": {"latitude": -33.0, "longitude": 151.0},
                    "vin": "vin-secret",
                    "ts": 1_787_140_800_000,
                },
                "chargingPreferences": {
                    "assetMaxRateOfChargeWatts": 7_200,
                    "assetMinRateOfChargeWatts": 1_400,
                    "batteryCapacityWh": 75_000,
                    "minBatterySocPercent": 20,
                    "maxBatterySocPercent": 90,
                    "optimisationType": "COST",
                    "tariff": "EV",
                    "monday": "OVERNIGHT",
                    "tariffPeriods": [
                        {"timeStart": "00:00", "timeEnd": "06:00", "ratePence": 8}
                    ],
                },
                "vendorSpecific": {
                    "tesla": {
                        "certificateInstallUrl": "https://secret.example/token",
                        "isCertificateInstalled": True,
                    }
                },
            }
        ],
        [
            {
                "_document_id": "device-secret",
                "inclusiveStartDate": "2026-08-01T00:00:00Z",
                "exclusiveEndDate": "2026-09-01T00:00:00Z",
                "totals": {
                    "total": {
                        "imported": {
                            "kwh": 44.2,
                            "cost": {"value": 3.54},
                            "rates": [
                                {
                                    "rate": {"timingCategory": "EV_OFFPEAK"},
                                    "kwh": 40,
                                    "cost": {"value": 3.2},
                                }
                            ],
                        }
                    }
                },
                "periods": [],
            }
        ],
        {
            "device-secret": {
                "updatedAt": "2026-08-19T12:00:00Z",
                "virtualDeviceID": "device-secret",
                "chargePlan": [
                    {
                        "startTimeInclusive": "2099-08-19T13:00:00Z",
                        "endTimeExclusive": "2099-08-19T15:00:00Z",
                        "shouldCharge": True,
                        "chargeLimitPercent": 80,
                        "predictedFinalBatteryPercent": 81,
                        "reason": "OPTIMISED",
                    }
                ],
            }
        },
        {
            "device-secret": {
                "virtualDeviceID": "device-secret",
                "tariffID": "tariff-secret",
                "chargingTimesMode": "ADVANCED",
                "demandPeriodChargingEnabled": True,
                "tariffRateChargingPeriods": [
                    {
                        "timingCategory": "EV_OFFPEAK",
                        "advancedChargeLimitPercent": 90,
                        "isSelectedInBasic": True,
                    }
                ],
            }
        },
    )


def test_vehicle_payload_exposes_full_safe_surface_and_redacts_identifiers():
    vehicles = _sample_vehicle_data()
    assert len(vehicles) == 1
    vehicle = vehicles[0]
    assert vehicle["battery_soc_percent"] == 62.5
    assert vehicle["battery_capacity_kwh"] == 75.0
    assert vehicle["preferences"]["weekdays"] == {"monday": "OVERNIGHT"}
    assert vehicle["charge_plan"]["intervals"][0]["reason"] == "OPTIMISED"
    assert vehicle["charging_times"]["demand_period_charging_enabled"] is True
    assert vehicle["monthly_energy"]["kwh"] == 44.2
    assert vehicle["monthly_energy"]["rates"][0]["timing_category"] == "EV_OFFPEAK"
    assert vehicle["certificate_installed"] is True

    rendered = repr(vehicles)
    for secret in (
        "device-secret",
        "account-secret",
        "user-secret",
        "signal-secret",
        "vin-secret",
        "tariff-secret",
        "secret.example",
        "-33.0",
        "151.0",
    ):
        assert secret not in rendered
    for forbidden_key in ("vin", "location", "is_at_home", "retail_account_number"):
        assert forbidden_key not in rendered.lower()


def test_unmatched_energy_is_not_duplicated_across_multiple_vehicles():
    vehicles = build_vehicle_data(
        "account",
        [],
        [
            {"_document_id": "vehicle-one", "vehicleModel": "One"},
            {"_document_id": "vehicle-two", "vehicleModel": "Two"},
        ],
        [{"_document_id": "unmatched", "totals": {}}],
        {},
        {},
    )

    assert len(vehicles) == 2
    assert all(vehicle["monthly_energy"] == {} for vehicle in vehicles)


def test_vehicle_sensors_surface_metrics_and_rich_attributes():
    vehicle = _sample_vehicle_data()[0]
    coordinator = MagicMock()
    coordinator.account_id = "account-secret"
    coordinator.account_device_id = "account-device-id"
    coordinator.last_update_success = True
    coordinator.data = {"vehicles": [vehicle]}

    battery_definition = next(item for item in VEHICLE_SENSOR_DEFINITIONS if item[0] == "battery_soc")
    battery = OVOVehicleMetricSensor(coordinator, vehicle, battery_definition)
    assert battery.native_value == 62.5
    assert "device-secret" not in battery._attr_unique_id
    assert battery.device_info["via_device_id"] == "account-device-id"
    assert "via_device" not in battery.device_info

    status = OVOVehicleStatusSensor(coordinator, vehicle)
    assert status.native_value == "Registered"
    assert status.extra_state_attributes["control_ready"] is True

    preferences = OVOVehiclePreferencesSensor(coordinator, vehicle)
    assert preferences.native_value == "COST"
    assert preferences.extra_state_attributes["tariff_periods"][0]["rate"] == 8

    schedule = OVOVehicleScheduleSensor(coordinator, vehicle)
    assert schedule.native_value == "ADVANCED"
    assert schedule.extra_state_attributes["periods"][0]["selected_in_basic"] is True

    plan = OVOVehicleChargePlanSensor(coordinator, vehicle)
    assert plan.native_value == "Scheduled"
    assert plan.extra_state_attributes["next_interval"]["charge_limit_percent"] == 80

    complete_set = create_vehicle_sensors(coordinator, vehicle)
    assert len(complete_set) == 19
    assert len({sensor._attr_unique_id for sensor in complete_set}) == 19
