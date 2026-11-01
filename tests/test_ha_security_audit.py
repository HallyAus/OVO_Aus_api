"""The HA backport audit must retain complete and conservative coverage."""

import hashlib
import json
import subprocess
import sys
import sysconfig
import venv
import zipfile
from pathlib import Path

import pytest

from scripts import audit_ha_security_runtime as audit

build = audit.build


def _inventory():
    return [
        {"name": "homeassistant", "version": build.LOCAL_VERSION},
        {"name": "Pillow", "version": build.PILLOW_VERSION},
        {"name": "PyJWT", "version": "2.15.1"},
    ]


def _report(inventory):
    return {"dependencies": [{"name": name, "version": version, "vulns": []}
                             for name, version in inventory.items()], "fixes": []}


@pytest.fixture
def provenance(tmp_path):
    wheel = tmp_path / f"homeassistant-{build.LOCAL_VERSION}-py3-none-any.whl"
    metadata = (
        "Metadata-Version: 2.4\nName: homeassistant\n"
        f"Version: {build.LOCAL_VERSION}\nRequires-Dist: Pillow=={build.PILLOW_VERSION}\n"
    )
    constants = (
        "MAJOR_VERSION: int = 2026\nMINOR_VERSION: int = 10\nPATCH_VERSION: str = '4'\n"
        f"SECURITY_BACKPORT: str = '{build.SECURITY_BACKPORT}'\n"
        f"__version__ = '{build.BASE_VERSION}'\n"
    )
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("homeassistant/__init__.py", "")
        archive.writestr("homeassistant/const.py", constants)
        archive.writestr(f"homeassistant-{build.LOCAL_VERSION}.dist-info/METADATA", metadata)
        archive.writestr(f"homeassistant-{build.LOCAL_VERSION}.dist-info/RECORD", "rewritten on installation\n")
    data = {
        "schema_version": 1,
        "purpose": "OVO CI security runtime; not an official Home Assistant release",
        "upstream_repository": "https://github.com/home-assistant/core",
        "base_version": build.BASE_VERSION,
        "base_commit": build.BASE_COMMIT,
        "source_url": build.SOURCE_URL,
        "source_sha256": build.SOURCE_SHA256,
        "source_date_epoch": build.SOURCE_DATE_EPOCH,
        "upstream_pillow13_commit": build.UPSTREAM_PILLOW_COMMIT,
        "upstream_patch_sha256": build.UPSTREAM_PATCH_SHA256,
        "backport_patch_sha256": build.BACKPORT_PATCH_SHA256,
        "local_version": build.LOCAL_VERSION,
        "runtime_version": build.BASE_VERSION,
        "security_backport": build.SECURITY_BACKPORT,
        "pillow_version": build.PILLOW_VERSION,
        "pin_files": list(build.PIN_FILES),
        "identity_files": list(build.IDENTITY_FILES),
        "build_frontend": build.BUILD_FRONTEND,
        "upstream_build_backend": build.UPSTREAM_BUILD_BACKEND,
        "build_backend": build.BUILD_BACKEND,
        "build_backend_advisory": build.BUILD_BACKEND_ADVISORY,
        "build_backend_fix_commit": build.BUILD_BACKEND_FIX_COMMIT,
        "wheel_filename": wheel.name,
        "wheel_sha256": build.file_sha256(wheel),
        "wheel_size_bytes": wheel.stat().st_size,
    }
    path = tmp_path / "provenance.json"
    path.write_text(json.dumps(data))
    return path, data, wheel


def test_provenance_binds_exact_backport_and_every_wheel_file(provenance):
    path, data, wheel = provenance
    result, manifest = audit.verified_provenance(path)
    assert result == data
    with zipfile.ZipFile(wheel) as archive:
        expected = {name: hashlib.sha256(archive.read(name)).hexdigest()
                    for name in archive.namelist() if not name.endswith("/RECORD")}
    assert manifest == expected


@pytest.mark.parametrize("field,value", [
    ("base_version", "2026.11.0b1"),
    ("base_commit", "0" * 40),
    ("source_sha256", "0" * 64),
    ("source_url", "https://untrusted.example/source.tar.gz"),
    ("backport_patch_sha256", "0" * 64),
    ("local_version", "2026.10.4+unreviewed"),
    ("runtime_version", build.LOCAL_VERSION),
    ("security_backport", "unreviewed"),
    ("purpose", "Official Home Assistant release"),
    ("build_backend", "unreviewed-backend"),
    ("build_backend", build.UPSTREAM_BUILD_BACKEND),
    ("upstream_build_backend", "unreviewed-backend"),
    ("build_backend_advisory", "unreviewed-advisory"),
    ("build_backend_fix_commit", "0" * 40),
    ("pin_files", []),
])
def test_provenance_rejects_changed_origin_or_identity(provenance, field, value):
    path, data, _ = provenance
    data[field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(audit.AuditError, match="provenance"):
        audit.verified_provenance(path)


def test_provenance_rejects_artifact_tampering(provenance):
    path, _, wheel = provenance
    with wheel.open("ab") as output:
        output.write(b"changed artifact")
    with pytest.raises(audit.AuditError, match="hash or size"):
        audit.verified_provenance(path)


def test_provenance_rejects_wheel_path_traversal(provenance):
    path, data, _ = provenance
    data["wheel_filename"] = "../untrusted.whl"
    path.write_text(json.dumps(data))
    with pytest.raises(audit.AuditError, match="filename"):
        audit.verified_provenance(path)


@pytest.mark.parametrize("extra", [
    {"name": "PyJWT", "version": "2.15.1+unreviewed"},
    {"name": "private-package", "version": "1.0+unreviewed"},
    {"name": "homeassistant", "version": "2026.10.4+unreviewed"},
])
def test_only_the_reviewed_local_identity_can_receive_base_coverage(extra):
    rows = [row for row in _inventory() if row["name"].lower() != extra["name"].lower()] + [extra]
    with pytest.raises(audit.AuditError, match="Unexpected local"):
        audit.dependency_inventory(rows)


@pytest.mark.parametrize("row", [
    {"name": "invalid\n--index-url", "version": "1.0"},
    {"name": "some-package", "version": "1.0\n-r untrusted.txt"},
])
def test_inventory_cannot_inject_requirement_options(row):
    with pytest.raises(audit.AuditError, match="Invalid installed"):
        audit.dependency_inventory([*_inventory(), row])


def test_inventory_rejects_duplicate_names_after_normalization():
    rows = [*_inventory(), {"name": "some_package", "version": "1.0"}, {"name": "some-package", "version": "1.0"}]
    with pytest.raises(audit.AuditError, match="Duplicate installed"):
        audit.dependency_inventory(rows)


def test_malformed_inventory_and_report_fail_closed():
    with pytest.raises(audit.AuditError, match="metadata"):
        audit.dependency_inventory([None])
    with pytest.raises(audit.AuditError, match="Invalid audit report"):
        audit.verify_audit_report([], {}, returncode=0)


def test_an_unlabeled_pillow_override_is_not_the_reviewed_backport():
    rows = _inventory()
    rows[0]["version"] = build.BASE_VERSION
    with pytest.raises(audit.AuditError, match="explicitly labeled"):
        audit.dependency_inventory(rows)


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "skip", "missing_vulns", "local_rewritten", "vulnerable"])
def test_audit_report_cannot_hide_missing_or_unsafe_distributions(mutation):
    expected = audit.dependency_inventory(_inventory())
    report = _report(expected)
    rows = report["dependencies"]
    if mutation == "missing":
        rows.pop()
    elif mutation == "extra":
        rows.append({"name": "unrequested", "version": "1.0", "vulns": []})
    elif mutation == "duplicate":
        rows.append(rows[0].copy())
    elif mutation == "skip":
        rows[0]["skip_reason"] = "not found"
    elif mutation == "missing_vulns":
        del rows[0]["vulns"]
    elif mutation == "local_rewritten":
        rows[0]["version"] = build.BASE_VERSION
    else:
        rows[0]["vulns"] = [{"id": "known-vulnerability"}]
    with pytest.raises(audit.AuditError):
        audit.verify_audit_report(report, expected, returncode=0)


def test_audit_requires_successful_service_exit_even_with_an_empty_vulnerability_list():
    expected = audit.dependency_inventory(_inventory())
    with pytest.raises(audit.AuditError, match="did not complete"):
        audit.verify_audit_report(_report(expected), expected, returncode=1)


@pytest.mark.parametrize("upstream_vulnerable", [False, True])
def test_both_actual_local_and_public_base_audits_are_required(tmp_path, monkeypatch, upstream_vulnerable):
    installed = audit.dependency_inventory(_inventory())
    monkeypatch.setattr(audit, "verified_provenance", lambda path: ({"verified": True}, {"one-file": "digest"}))
    monkeypatch.setattr(audit, "collect_runtime", lambda python, manifest: ({"distributions": _inventory()}, installed))
    calls = []

    def run(command, **kwargs):
        assert command[:4] == [sys.executable, "-I", "-m", "pip_audit"]
        assert {"--strict", "--no-deps", "--disable-pip"}.issubset(command)
        assert not {"--ignore-vuln", "--skip-editable", "--fix", "--dry-run"}.intersection(command)
        service = command[command.index("--vulnerability-service") + 1]
        requirements = Path(command[command.index("-r") + 1]).read_text().splitlines()
        actual = dict(line.split("==") for line in requirements)
        calls.append((service, actual))
        report = _report(actual)
        returncode = 0
        if service == "pypi" and upstream_vulnerable:
            report["dependencies"][0]["vulns"] = [{"id": "affected-public-base-boundary"}]
            returncode = 1
        Path(command[command.index("-o") + 1]).write_text(json.dumps(report))
        return subprocess.CompletedProcess(command, returncode, stdout="", stderr="")

    monkeypatch.setattr(audit.subprocess, "run", run)
    output_dir = tmp_path / "audit"
    if upstream_vulnerable:
        with pytest.raises(audit.AuditError, match="Known vulnerabilities"):
            audit.audit_runtime(sys.executable, sys.executable, tmp_path / "provenance.json", output_dir)
    else:
        summary = audit.audit_runtime(sys.executable, sys.executable, tmp_path / "provenance.json", output_dir)
        assert summary["status"] == "passed"
    assert calls == [("osv", installed), ("pypi", {"homeassistant": build.BASE_VERSION})]
    summary = json.loads((output_dir / "summary.json").read_text())
    assert summary["status"] == ("failed" if upstream_vulnerable else "passed")


@pytest.mark.parametrize("tamper", [False, True])
def test_real_runtime_inventory_checks_installed_files_before_import(provenance, tmp_path, tamper):
    path, _, wheel = provenance
    _, manifest = audit.verified_provenance(path)
    environment = tmp_path / "runtime"
    venv.EnvBuilder(with_pip=False, symlinks=sys.platform != "win32").create(environment)
    python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    purelib = Path(sysconfig.get_path("purelib", vars={"base": str(environment), "platbase": str(environment)}))
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            target = purelib / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    pillow = purelib / f"pillow-{build.PILLOW_VERSION}.dist-info"
    pillow.mkdir()
    (pillow / "METADATA").write_text(f"Name: Pillow\nVersion: {build.PILLOW_VERSION}\n")
    marker = tmp_path / "unsafe-import-executed"
    if tamper:
        (purelib / "homeassistant/__init__.py").write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
        with pytest.raises(audit.AuditError, match="installed-wheel verification"):
            audit.collect_runtime(str(python), manifest)
        assert not marker.exists()
    else:
        runtime, inventory = audit.collect_runtime(str(python), manifest)
        assert inventory == {"homeassistant": build.LOCAL_VERSION, "pillow": build.PILLOW_VERSION}
        assert runtime["verified_wheel_files"] == len(manifest)
