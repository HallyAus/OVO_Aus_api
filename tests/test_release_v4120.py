"""Protect release metadata, referral notes and the scoped publication path."""

import json
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_source_versions_agree_with_prepared_release():
    manifest = json.loads((ROOT / "custom_components/ovo_energy_au/manifest.json").read_text())
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert manifest["version"] == project["project"]["version"] == "4.12.0"
    version = manifest["version"]
    assert (ROOT / f"docs/releases/v{version}.md").is_file()


@pytest.mark.parametrize("referral", [
    "daniel16485",
    "https://www.ovoenergy.com.au/refer/daniel16485",
    "https://ovoreferralcode.com/",
])
def test_referral_is_prominent_in_release_notes(referral):
    notes = (ROOT / "docs/releases/v4.12.0.md").read_text()
    assert referral in notes.split("---", 1)[0]


def test_one_release_request_does_not_remove_the_exact_source_ci_gate():
    workflow = (ROOT / ".github/workflows/release.yml").read_text()
    assert "github.event.ref_type == 'branch' && github.event.ref == 'release/v4.12.0'" in workflow
    assert workflow.count("github.event_name == 'create' && 'v4.12.0'") == 2
    assert "v4.11.0" not in workflow
    assert "github.repository == 'HallyAus/OVO_Aus_api'" in workflow
    assert "actions: read" in workflow
    assert "actions: write" not in workflow
    gate = workflow.index("python scripts/verify_github_release.py")
    package = workflow.index("python scripts/package_github_release.py")
    publish = workflow.index("- name: Create GitHub Release")
    verify = workflow.index("- name: Verify the published tag, referral and downloaded release ZIP")
    assert gate < package < publish < verify
    assert "continue-on-error" not in workflow
    assert "fail_on_unmatched_files: true" in workflow
