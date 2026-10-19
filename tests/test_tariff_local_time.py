"""The current tariff period follows Home Assistant's time zone, not Sydney's (#86)."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from custom_components.ovo_energy_au import sensor as sensor_mod


def _sensor():
    sensor = object.__new__(sensor_mod.OVOTariffPeriodSensor)
    sensor.coordinator = SimpleNamespace(plan_config=object(), data={})
    return sensor


def test_period_hour_uses_home_assistant_local_time():
    # 13:33 in Adelaide is 14:03 in Sydney during daylight saving.
    local = datetime(2026, 10, 19, 13, 33, tzinfo=ZoneInfo("Australia/Adelaide"))
    with patch.object(sensor_mod.dt_util, "now", return_value=local), patch.object(
        sensor_mod, "get_tariff_details", return_value={}
    ) as details:
        _sensor()._period_details()
    assert details.call_args.args[2] == 13
