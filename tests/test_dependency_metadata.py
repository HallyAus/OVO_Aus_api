"""Supported host/runtime metadata must retain the integration's dependency contract."""
import json
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]


def test_core_pyjwt_is_not_reinstalled_by_the_custom_integration():
    manifest = json.loads((ROOT / "custom_components/ovo_energy_au/manifest.json").read_text())
    names = {Requirement(item).name.casefold() for item in manifest["requirements"]}
    assert "pyjwt" not in names


def test_package_keeps_the_jwt_security_floor_and_major_compatibility_bound():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    jwt = next(Requirement(item) for item in project["project"]["dependencies"]
               if Requirement(item).name.casefold() == "pyjwt")
    assert jwt.specifier == SpecifierSet(">=2.13.0,<3.0.0")
    assert Version("2.13.0") in jwt.specifier
    assert Version("2.12.1") not in jwt.specifier
    assert Version("3.0.0") not in jwt.specifier


def test_hacs_retains_the_first_verified_compatible_home_assistant_minimum():
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert hacs["homeassistant"] == "2026.8.3"
