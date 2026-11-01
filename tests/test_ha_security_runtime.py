"""The custom HA build must retain provenance and reject unreviewed changes."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import tarfile
import tomllib
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

_spec = importlib.util.spec_from_file_location(
    "build_ha_security_runtime",
    Path(__file__).resolve().parents[1] / "scripts/build_ha_security_runtime.py",
)
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)


@pytest.fixture
def upstream_source(tmp_path):
    """Minimal source for the precise dependency and identity transformation."""
    source = tmp_path / "source"
    for name in builder.PIN_FILES:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('Pillow==12.3.0\nunchanged-upstream-data\n')
    (source / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["setuptools==84.0.0"]\n'
        'build-backend = "setuptools.build_meta"\n'
        '[project]\nname = "homeassistant"\nversion = "2026.10.4"\n'
        'dependencies = ["Pillow==12.3.0", "other==1.0"]\n'
    )
    (source / "homeassistant/const.py").write_text(
        'from typing import Final\nMAJOR_VERSION: Final = 2026\n'
        'MINOR_VERSION: Final = 10\nPATCH_VERSION: Final = "4"\n'
        '__short_version__: Final = f"{MAJOR_VERSION}.{MINOR_VERSION}"\n'
        '__version__: Final = f"{__short_version__}.{PATCH_VERSION}"\n'
    )
    return source


def test_checked_in_patches_have_reviewed_hashes_and_exact_file_scopes():
    builder.verified_patch(
        builder.PATCH_DIRECTORY / "homeassistant-upstream-pillow13.patch",
        builder.UPSTREAM_PATCH_SHA256, set(builder.PIN_FILES),
    )
    builder.verified_patch(
        builder.PATCH_DIRECTORY / "homeassistant-2026.10.4-pillow13.patch",
        builder.BACKPORT_PATCH_SHA256, set(builder.PIN_FILES) | set(builder.IDENTITY_FILES),
    )


def test_modified_patch_is_rejected_before_execution(tmp_path):
    target = tmp_path / "altered.patch"
    target.write_bytes(b"modified contents")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        builder.verified_patch(target, builder.BACKPORT_PATCH_SHA256, set(builder.PIN_FILES))


def test_patch_scope_cannot_expand_even_with_an_updated_digest(tmp_path):
    contents = b"diff --git a/unreviewed.py b/unreviewed.py\n"
    target = tmp_path / "out-of-scope.patch"
    target.write_bytes(contents)
    with pytest.raises(ValueError, match="file scope"):
        builder.verified_patch(target, hashlib.sha256(contents).hexdigest(), {"pyproject.toml"})


def test_source_hash_is_checked_before_any_extraction(tmp_path):
    archive = tmp_path / "untrusted.tar.gz"
    archive.write_bytes(b"not the pinned source")
    destination = tmp_path / "extracted"
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        builder.extract_source(archive, destination)
    assert not destination.exists()


@pytest.mark.parametrize("name", [
    f"core-{builder.BASE_COMMIT}/../escape",
    f"core-{builder.BASE_COMMIT}/absolute/../../escape",
    f"core-{builder.BASE_COMMIT}/directory\\escape",
    f"core-{builder.BASE_COMMIT}/drive:escape",
    f"core-{builder.BASE_COMMIT}/directory//file",
    f"core-{builder.BASE_COMMIT}/file\nname",
    "/absolute",
    "another-revision/homeassistant/const.py",
])
def test_archive_rejects_unsafe_or_wrong_revision_paths(name):
    with pytest.raises(ValueError, match="Unsafe source"):
        builder.archive_member_path(tarfile.TarInfo(name))


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE])
def test_archive_cannot_extract_links_or_special_files(kind):
    member = tarfile.TarInfo(f"core-{builder.BASE_COMMIT}/homeassistant/escape")
    member.type = kind
    member.linkname = "/outside"
    with pytest.raises(ValueError, match="link or special"):
        builder.archive_member_path(member)


def test_only_exact_known_nonpackage_links_are_recognized():
    member = tarfile.TarInfo(f"core-{builder.BASE_COMMIT}/CLAUDE.md")
    member.type = tarfile.SYMTYPE
    member.linkname = "AGENTS.md"
    assert builder.archive_member_path(member) == "CLAUDE.md"
    member.linkname = "../../escape"
    with pytest.raises(ValueError, match="link or special"):
        builder.archive_member_path(member)


def test_duplicate_archive_member_rejected_before_any_writes(tmp_path, monkeypatch):
    archive = tmp_path / "duplicate.tar.gz"
    with tarfile.open(archive, "w:gz") as file:
        for _ in range(2):
            member = tarfile.TarInfo(f"core-{builder.BASE_COMMIT}/file")
            member.size = 1
            file.addfile(member, io.BytesIO(b"x"))
    monkeypatch.setattr(builder, "SOURCE_SHA256", builder.file_sha256(archive))
    destination = tmp_path / "extracted"
    with pytest.raises(ValueError, match="Duplicate"):
        builder.extract_source(archive, destination)
    assert not destination.exists()


def test_full_backport_changes_only_pins_and_explicit_distribution_identity(upstream_source):
    expected = builder.expected_backport_contents(upstream_source)
    assert set(expected) == set(builder.PIN_FILES) | set(builder.IDENTITY_FILES)
    for name in builder.PIN_FILES:
        assert expected[name].count(b"Pillow==13.0.0") == 1
        assert b"Pillow==12.3.0" not in expected[name]
    assert b'other==1.0' in expected["pyproject.toml"]
    assert f'version = "{builder.LOCAL_VERSION}"'.encode() in expected["pyproject.toml"]
    constants = builder.runtime_constants(expected["homeassistant/const.py"])
    assert constants["PATCH_VERSION"] == "4"
    assert constants["SECURITY_BACKPORT"] == "ovo.pillow13.1"
    assert (upstream_source / "homeassistant/package_constraints.txt").read_text().startswith("Pillow==12.3.0")


def test_build_backend_fix_is_explicit_and_preserves_original_source_expectation(upstream_source):
    original = tomllib.loads((upstream_source / "pyproject.toml").read_text())
    patched = tomllib.loads(builder.expected_backport_contents(upstream_source)["pyproject.toml"].decode())
    assert original["build-system"]["requires"] == ["setuptools==84.0.0"]
    assert patched["build-system"]["requires"] == ["setuptools==84.1.0"]
    assert patched["build-system"]["build-backend"] == original["build-system"]["build-backend"]
    assert patched["project"]["dependencies"] == ["Pillow==13.0.0", "other==1.0"]
    assert builder.BUILD_BACKEND_ADVISORY == "GHSA-xmj3-9gf7-h52w"


@pytest.mark.parametrize("change", [
    "missing_pin", "duplicate_pin", "wrong_base", "wrong_backend", "already_fixed_backend", "already_custom",
])
def test_unexpected_source_cannot_be_silently_rebased(upstream_source, change):
    if change in {"missing_pin", "duplicate_pin"}:
        target = upstream_source / "homeassistant/package_constraints.txt"
        target.write_text("Pillow==12.2.0\n" if change == "missing_pin" else "Pillow==12.3.0\n" * 2)
    elif change in {"wrong_base", "wrong_backend", "already_fixed_backend"}:
        target = upstream_source / "pyproject.toml"
        original, replacement = {
            "wrong_base": ("2026.10.4", "2026.10.5"),
            "wrong_backend": ("setuptools==84.0.0", "unreviewed-build-backend"),
            "already_fixed_backend": ("setuptools==84.0.0", "setuptools==84.1.0"),
        }[change]
        target.write_text(target.read_text().replace(original, replacement))
    else:
        target = upstream_source / "homeassistant/const.py"
        target.write_text(target.read_text() + 'SECURITY_BACKPORT = "other"\n')
    with pytest.raises(ValueError, match="Unexpected upstream"):
        builder.expected_backport_contents(upstream_source)


def test_patch_application_result_is_verified_byte_for_byte(upstream_source):
    expected = builder.expected_backport_contents(upstream_source)

    def corrupt_apply(*args, **kwargs):
        for name, contents in expected.items():
            (upstream_source / name).write_bytes(contents)
        (upstream_source / "homeassistant/package_constraints.txt").write_text("Pillow==12.3.0\n")

    with patch.object(builder.shutil, "which", return_value="/usr/bin/git"), \
            patch.object(builder.subprocess, "run", side_effect=corrupt_apply), \
            pytest.raises(ValueError, match="more than the allowed"):
        builder.apply_backport(upstream_source, b"verified patch", io.StringIO())


def _wheel(tmp_path, expected, *, metadata_version=None, pillow="13.0.0", altered=None):
    wheel = tmp_path / f"homeassistant-{builder.LOCAL_VERSION}-py3-none-any.whl"
    metadata = (
        "Metadata-Version: 2.4\nName: homeassistant\n"
        f"Version: {metadata_version or builder.LOCAL_VERSION}\n"
        f"Requires-Dist: Pillow=={pillow}\n"
    )
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(f"homeassistant-{builder.LOCAL_VERSION}.dist-info/METADATA", metadata)
        for name, contents in expected.items():
            if name.startswith("homeassistant/"):
                archive.writestr(name, altered[1] if altered and altered[0] == name else contents)
    return wheel


def test_verified_wheel_records_exact_artifact_and_preserves_runtime_calendar_version(upstream_source, tmp_path):
    expected = builder.expected_backport_contents(upstream_source)
    wheel = _wheel(tmp_path, expected)
    result = builder.verify_wheel(wheel, expected)
    assert result["wheel_sha256"] == builder.file_sha256(wheel)
    assert result["wheel_filename"] == wheel.name
    assert result["wheel_size_bytes"] == wheel.stat().st_size


@pytest.mark.parametrize("change", ["distribution", "metadata_pin", "constraint", "manifest", "runtime"])
def test_built_wheel_cannot_revert_pins_or_hide_its_identity(upstream_source, tmp_path, change):
    expected = builder.expected_backport_contents(upstream_source)
    arguments = {}
    if change == "distribution":
        arguments["metadata_version"] = builder.BASE_VERSION
    elif change == "metadata_pin":
        arguments["pillow"] = "12.3.0"
    else:
        name = {
            "constraint": "homeassistant/package_constraints.txt",
            "manifest": "homeassistant/components/generic/manifest.json",
            "runtime": "homeassistant/const.py",
        }[change]
        arguments["altered"] = (name, b"unreviewed contents")
    wheel = _wheel(tmp_path, expected, **arguments)
    with pytest.raises(ValueError, match="mismatch"):
        builder.verify_wheel(wheel, expected)


def test_build_environment_excludes_secrets_python_injection_and_custom_indexes(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "example-secret")
    monkeypatch.setenv("MY_CUSTOM_SECRET", "example-secret")
    monkeypatch.setenv("PYTHONPATH", "/untrusted/imports")
    monkeypatch.setenv("PIP_INDEX_URL", "https://untrusted.invalid/simple")
    monkeypatch.setenv("PIP_EXTRA_INDEX_URL", "https://untrusted.invalid/extra")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    environment = builder.build_environment()
    assert not {"GITHUB_TOKEN", "MY_CUSTOM_SECRET", "PYTHONPATH", "PIP_EXTRA_INDEX_URL", "GIT_CONFIG_COUNT"} & environment.keys()
    assert environment["PIP_INDEX_URL"] == "https://pypi.org/simple"
    assert environment["SOURCE_DATE_EPOCH"] == builder.SOURCE_DATE_EPOCH


def test_build_refuses_an_existing_output_directory_before_any_network(tmp_path):
    with patch.object(builder, "download_source") as download, pytest.raises(ValueError, match="fresh path"):
        builder.build_security_runtime(tmp_path)
    download.assert_not_called()


def test_build_refuses_symlink_output_without_following_it(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    output = tmp_path / "output"
    output.symlink_to(target, target_is_directory=True)
    with patch.object(builder, "download_source") as download, pytest.raises(ValueError, match="fresh path"):
        builder.build_security_runtime(output)
    download.assert_not_called()
    assert not list(target.iterdir())


def test_pinned_source_endpoint_cannot_redirect():
    with pytest.raises(ValueError, match="Unexpected redirect"):
        builder._NoRedirect().redirect_request(None, None, 302, "Found", {}, "http://untrusted.invalid/source")
