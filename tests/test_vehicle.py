"""Kaluza vehicle decoding, privacy, and sensor regression tests."""

from unittest.mock import MagicMock

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
    build_vehicle_data,
    decode_firestore_documents,
    decode_firestore_value,
)


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def raise_for_status(self):
        return None

    async def json(self):
        return self._payload


class _FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, headers):
        self.calls.append((url, headers))
        if url.endswith("/token"):
            return _FakeResponse(
                {"idToken": "flex-token", "userId": "user-id", "expiresIn": 900}
            )
        return _FakeResponse({})


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
    assert await client.async_get_vehicle_data("account", "myovo-token") == []
    assert await client.async_get_vehicle_data("account", "myovo-token") == []

    token_calls = [call for call in session.calls if call[0].endswith("/token")]
    assert len(token_calls) == 1
    assert token_calls[0][1]["authorization"] == "Bearer myovo-token"
    data_calls = [call for call in session.calls if not call[0].endswith("/token")]
    assert data_calls
    assert all(call[1]["authorization"] == "Bearer flex-token" for call in data_calls)
    assert all("/users/user-id/" in call[0] for call in data_calls)
    assert all(call[0].startswith("https://") for call in session.calls)


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
    coordinator.last_update_success = True
    coordinator.data = {"vehicles": [vehicle]}

    battery_definition = next(item for item in VEHICLE_SENSOR_DEFINITIONS if item[0] == "battery_soc")
    battery = OVOVehicleMetricSensor(coordinator, vehicle, battery_definition)
    assert battery.native_value == 62.5
    assert "device-secret" not in battery._attr_unique_id
    assert battery.device_info["via_device"] == ("ovo_energy_au", "account-secret")

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
