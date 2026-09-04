"""Regressions found by the September reliability review; no live accounts."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.ovo_energy_au.analytics.interval import process_interval_data
from custom_components.ovo_energy_au.api import (
    OVOEnergyAUApiClient,
    OVOEnergyAUApiClientAuthenticationError,
    OVOEnergyAUApiClientCommunicationError,
    OVOEnergyAUApiClientError,
)
from custom_components.ovo_energy_au.const import AU_TIMEZONE
from custom_components.ovo_energy_au.models import PlanConfig
from custom_components.ovo_energy_au.sensor import OVOEnergyDashboardSensor, OVOPlanSensor
from custom_components.ovo_energy_au.sensors.base import get_hourly_data_for_date, parse_entry_timestamp
from custom_components.ovo_energy_au.tariffs import get_current_product, get_tariff_details


def reading(start, consumption, direction="DEBIT", rate="OTHER"):
    return {
        "periodFrom": start,
        "consumption": consumption,
        "charge": {"type": direction, "value": consumption / 10},
        "rates": [{"type": rate, "consumption": consumption,
                   "charge": {"type": direction, "value": consumption / 10}}],
    }


@pytest.mark.parametrize("key,source", [("grid_consumption", "grid_latest"),
                                        ("return_to_grid", "grid_latest"),
                                        ("solar_consumption", "solar_latest")])
def test_energy_reset_uses_source_period_not_wall_clock(key, source):
    coordinator = SimpleNamespace(account_id="fixture", data={"monthly": {
        key: 123.4, source: {"periodFrom": "2000-01-31T13:00:00Z"}}})
    sensor = OVOEnergyDashboardSensor(coordinator, "fixture", "Fixture", key, "mdi:flash")
    assert sensor.last_reset == datetime(2000, 2, 1, tzinfo=AU_TIMEZONE)
    assert sensor.native_value == 123.4


def test_energy_without_a_valid_period_is_unknown():
    coordinator = SimpleNamespace(account_id="fixture", data={"monthly": {"grid_consumption": 12}})
    sensor = OVOEnergyDashboardSensor(coordinator, "fixture", "Fixture", "grid_consumption", "mdi:flash")
    assert sensor.native_value is None
    assert sensor.last_reset is None


@pytest.mark.parametrize("period", ["daily", "monthly", "yearly"])
def test_interval_latest_is_chronological_not_last_array_element(period):
    latest = reading("2026-03-01T00:00:00+11:00", 8)
    older = reading("2026-02-01T00:00:00+11:00", 100)
    result = process_interval_data({period: {"solar": [latest, older], "export": [latest, older]}})
    assert result[period]["grid_consumption"] == 8
    assert result[period]["solar_consumption"] == 8


def test_export_credit_never_inflates_grid_rate_breakdown():
    entries = [reading("2026-03-19T00:00:00+11:00", 4, "DEBIT", "OTHER"),
               reading("2026-03-19T00:00:00+11:00", 7, "CREDIT", "FEED_IN_TARIFF")]
    result = process_interval_data({"daily": {"export": entries}, "monthly": {"export": entries}})
    assert result["daily"]["grid_consumption"] == 4
    assert result["daily"]["return_to_grid"] == 7
    assert set(result["daily"]["rate_breakdown"]) == {"OTHER"}
    assert result["daily"]["rate_breakdown"]["OTHER"]["percent"] == 100
    assert set(result["all_time"]["rate_breakdown"]) == {"OTHER"}
    assert set(result["all_daily_entries"][0]["grid_rates_kwh"]) == {"OTHER"}


def test_multiple_solar_readings_in_same_period_are_summed():
    entries = [reading("2026-03-19T00:00:00+11:00", 4), reading("2026-03-19T00:00:00+11:00", 7)]
    result = process_interval_data({"daily": {"solar": entries}})
    assert result["daily"]["solar_consumption"] == 11
    assert result["all_daily_entries"][0]["solar_consumption"] == 11


def test_no_hourly_samples_is_not_zero_usage():
    target = datetime(2026, 3, 19).date()
    data = {"hourly": {"grid_entries": [reading("2026-03-18T00:00:00+11:00", 1)]}}
    assert get_hourly_data_for_date(data, "grid_entries", target)["state"] is None
    assert get_hourly_data_for_date(data, "solar_entries", target)["state"] is None
    data["hourly"]["grid_entries"] = [reading("2026-03-19T00:00:00+11:00", 0)]
    assert get_hourly_data_for_date(data, "grid_entries", target)["state"] == 0


def test_naive_source_time_does_not_depend_on_host_timezone():
    assert parse_entry_timestamp("2026-03-19T03:00:00") == datetime(2026, 3, 19, 3, tzinfo=AU_TIMEZONE)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), "NaN", True])
def test_invalid_tariff_numbers_do_not_reach_entity_state(value):
    data = {"product_agreements": {"productAgreements": [{"product": {"unitRatesCentsPerKWH": {"peak": value}}}]}}
    assert get_tariff_details(PlanConfig(peak_rate=0.35), data, 9)["rate_cents_kwh"] == 35


@pytest.mark.parametrize("agreement", [
    {"fromDt": "2099-01-01", "toDt": None},
    {"fromDt": "1990-01-01", "toDt": "1999-01-01"},
])
def test_inactive_agreements_are_not_presented_as_current(agreement):
    assert get_current_product({"productAgreements": [{**agreement, "product": {"displayName": "The Free 4 Plan"}}]}) == {}


def test_nullable_product_rates_do_not_crash_plan_attributes():
    coordinator = SimpleNamespace(account_id="fixture", plan_config=PlanConfig(), data={
        "product_agreements": {"productAgreements": [{"product": {
            "displayName": "The Basic Plan", "unitRatesCentsPerKWH": None}}]}})
    assert OVOPlanSensor(coordinator).extra_state_attributes["plan_name"] == "The Basic Plan"


class Response:
    def __init__(self, payload=None, status=200, content_type="application/json"):
        self.payload = payload
        self.status = status
        self.headers = {"Content-Type": content_type}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(MagicMock(), (), status=self.status, message="private-provider-detail")

    async def json(self):
        return self.payload


class Session:
    def __init__(self, response):
        self.response = response

    def post(self, *args, **kwargs):
        return self.response


def client(response):
    result = OVOEnergyAUApiClient(Session(response), "fixture@example.invalid", "fixture-password")
    result.set_tokens("access", "identity", "refresh", expires_in=3600)
    result._rate_limit = AsyncMock()
    return result


@pytest.mark.asyncio
async def test_invalid_grant_refresh_falls_back_to_credentials():
    api = client(Response({"error": "invalid_grant"}, status=400))
    api._access_token = None
    api.authenticate_with_password = AsyncMock()
    await api._ensure_authenticated()
    api.authenticate_with_password.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_can_retain_identity_token_when_omitted():
    api = client(Response({"access_token": "new-access", "expires_in": 300}))
    await api.refresh_tokens()
    assert api._access_token == "new-access"
    assert api._id_token == "identity"
    assert api._refresh_token == "refresh"


@pytest.mark.asyncio
async def test_login_timeout_is_communication_failure_not_bad_password():
    session = MagicMock()
    session.get.side_effect = TimeoutError("private-provider-detail")
    api = OVOEnergyAUApiClient(session)
    with pytest.raises(OVOEnergyAUApiClientCommunicationError):
        await api.authenticate_with_password("fixture@example.invalid", "fixture-password")


@pytest.mark.asyncio
async def test_html_maintenance_is_not_auth_failure():
    api = client(Response(content_type="text/html"))
    with pytest.raises(OVOEnergyAUApiClientCommunicationError):
        await api._graphql_request("Fixture", "query Fixture {}", {}, "Fixture")


@pytest.mark.asyncio
async def test_graphql_provider_error_is_not_echoed():
    api = client(Response({"errors": [{"message": "private-provider-detail"}]}))
    with pytest.raises(OVOEnergyAUApiClientError) as raised:
        await api._graphql_request("Fixture", "query Fixture {}", {}, "Fixture")
    assert "private-provider-detail" not in str(raised.value)


@pytest.mark.asyncio
async def test_network_error_is_not_echoed_or_treated_as_auth_failure():
    api = client(Response(status=503))
    with pytest.raises(OVOEnergyAUApiClientCommunicationError) as raised:
        await api._graphql_request("Fixture", "query Fixture {}", {}, "Fixture")
    assert "private-provider-detail" not in str(raised.value)


@pytest.mark.asyncio
async def test_malformed_graphql_root_is_api_error():
    api = client(Response(["not an object"]))
    with pytest.raises(OVOEnergyAUApiClientError):
        await api._graphql_request("Fixture", "query Fixture {}", {}, "Fixture")


@pytest.mark.asyncio
async def test_optional_null_does_not_hide_missing_data_envelope():
    api = client(Response({"unexpected": True}))
    with pytest.raises(OVOEnergyAUApiClientError):
        await api._graphql_request("Fixture", "query Fixture {}", {}, "Fixture", allow_null_result=True)
    api = client(Response({"data": {"Fixture": None}}))
    assert await api._graphql_request("Fixture", "query Fixture {}", {}, "Fixture", allow_null_result=True) == {}


@pytest.mark.parametrize("automatic,expected", [(True, False), (False, True)])
def test_no_active_product_does_not_activate_automatic_tariff(automatic, expected):
    from custom_components.ovo_energy_au.sensor import OVOTariffPeriodSensor
    coordinator = SimpleNamespace(account_id="fixture", data={}, auto_detect_plan=automatic,
                                  last_update_success=True, plan_config=PlanConfig())
    assert OVOTariffPeriodSensor(coordinator).available is expected


@pytest.mark.asyncio
async def test_refresh_transport_failure_does_not_resubmit_password():
    api = client(Response())
    api._access_token = None
    api._session.post = MagicMock(side_effect=TimeoutError("private-provider-detail"))
    api.authenticate_with_password = AsyncMock()
    with pytest.raises(OVOEnergyAUApiClientCommunicationError):
        await api._ensure_authenticated()
    api.authenticate_with_password.assert_not_awaited()
    assert api._refresh_token == "refresh"


@pytest.mark.asyncio
async def test_incomplete_refresh_does_not_replace_existing_tokens():
    api = client(Response({"expires_in": 300}))
    with pytest.raises(OVOEnergyAUApiClientCommunicationError):
        await api.refresh_tokens()
    assert api._access_token == "access"
    assert api._id_token == "identity"
    assert api._refresh_token == "refresh"
