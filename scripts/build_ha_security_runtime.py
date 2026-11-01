"""Build the explicitly identified HA security runtime used by OVO's CI.

Requires Python >=3.14.2, Git, and ``build==1.6.1``. The isolated build backend
is explicitly patched from upstream's setuptools==84.0.0 to fixed 84.1.0.
This does not install or upgrade Home Assistant. The resulting wheel is a
local security backport, not an official Home Assistant release.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
import zipfile
from email.parser import BytesParser
from importlib.metadata import version
from pathlib import Path, PurePosixPath

BASE_VERSION = "2026.10.4"
SECURITY_BACKPORT = "ovo.pillow13.1"
LOCAL_VERSION = f"{BASE_VERSION}+{SECURITY_BACKPORT}"
PILLOW_VERSION = "13.0.0"
BASE_COMMIT = "357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b"  # pragma: allowlist secret -- public upstream Git commit
UPSTREAM_PILLOW_COMMIT = "ae6f8602aab71b21505ff0974e7440fbff4aac21"  # pragma: allowlist secret -- public upstream Git commit
SOURCE_URL = f"https://codeload.github.com/home-assistant/core/tar.gz/{BASE_COMMIT}"
SOURCE_SHA256 = "09023dea97cfe7d37ae70f4cedcbd3c9177da79ad3d5f5dfc469ff425f8d6432"  # pragma: allowlist secret -- public source archive digest
SOURCE_DATE_EPOCH = "1792872089"
UPSTREAM_PATCH_SHA256 = "bb995998e00f6ad6b8561dbd5f342a131c42caa04d0ae94fe871beb49555c835"  # pragma: allowlist secret -- checked-in public patch digest
BACKPORT_PATCH_SHA256 = "2929b83c9bb38cc7a5ef03d09c812f466df38f5769d6bee03f0b30e1e429af9c"  # pragma: allowlist secret -- checked-in public patch digest
BUILD_FRONTEND = "build==1.6.1"
UPSTREAM_BUILD_BACKEND = "setuptools==84.0.0"
BUILD_BACKEND = "setuptools==84.1.0"
BUILD_BACKEND_ADVISORY = "GHSA-xmj3-9gf7-h52w"
BUILD_BACKEND_FIX_COMMIT = "6d07b8d17890dda58d944ac51e58f54af92d52af"  # pragma: allowlist secret -- public setuptools security fix commit
PIN_FILES = (
    "homeassistant/components/doods/manifest.json",
    "homeassistant/components/generic/manifest.json",
    "homeassistant/components/image_upload/manifest.json",
    "homeassistant/components/matrix/manifest.json",
    "homeassistant/components/proxy/manifest.json",
    "homeassistant/components/qrcode/manifest.json",
    "homeassistant/components/seven_segments/manifest.json",
    "homeassistant/components/sighthound/manifest.json",
    "homeassistant/package_constraints.txt",
    "pyproject.toml",
    "requirements.txt",
    "requirements_all.txt",
)
IDENTITY_FILES = ("pyproject.toml", "homeassistant/const.py")
PATCH_DIRECTORY = Path(__file__).resolve().parent / "patches"
OMITTED_NONPACKAGE_SYMLINKS = {
    ".agent/skills": "../.claude/skills/",
    ".gemini/skills": "../.claude/skills",
    "CLAUDE.md": "AGENTS.md",
}
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_SOURCE_BYTES = 1024 * 1024 * 1024


def file_sha256(path: Path) -> str:
    """Hash an artifact without loading a source archive into memory."""
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def verified_patch(path: Path, digest: str, expected_files: set[str]) -> bytes:
    """Reject modified patches or an expansion of their reviewed file scope."""
    contents = path.read_bytes()
    if hashlib.sha256(contents).hexdigest() != digest:
        raise ValueError(f"Patch SHA-256 mismatch: {path.name}")
    headers = re.findall(rb"^diff --git a/(\S+) b/(\S+)$", contents, re.MULTILINE)
    if len(headers) != len(expected_files) or any(a != b for a, b in headers):
        raise ValueError("Unexpected patch file scope")
    if {a.decode() for a, _ in headers} != expected_files:
        raise ValueError("Unexpected patch file scope")
    return contents


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """The immutable source must come from the pinned HTTPS endpoint."""
        raise ValueError("Unexpected redirect while fetching the pinned source")


def download_source(destination: Path) -> None:
    """Fetch one fixed public HTTPS URL and verify it before extraction."""
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "ovo-ha-security-build/1"})
    opener = urllib.request.build_opener(_NoRedirect())
    digest = hashlib.sha256()
    size = 0
    with opener.open(request, timeout=30) as response, destination.open("xb") as output:
        if response.status != 200 or response.geturl() != SOURCE_URL:
            raise ValueError("Unexpected source download response")
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_ARCHIVE_BYTES:
                raise ValueError("Source archive exceeds the size limit")
            digest.update(chunk)
            output.write(chunk)
    if digest.hexdigest() != SOURCE_SHA256:
        raise ValueError("Source archive SHA-256 mismatch")


def archive_member_path(member: tarfile.TarInfo) -> str:
    """Allow canonical archive paths and only the three known documentation links."""
    name = member.name.rstrip("/")
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or "\\" in name or ":" in name
            or any(ord(char) < 32 for char in name)
            or any(part in {"", ".", ".."} for part in name.split("/"))
            or path.parts[0] != f"core-{BASE_COMMIT}"):
        raise ValueError("Unsafe source archive member path")
    relative = "/".join(path.parts[1:])
    if member.issym() and OMITTED_NONPACKAGE_SYMLINKS.get(relative) == member.linkname:
        return relative
    if not (member.isfile() or member.isdir()):
        raise ValueError("Unexpected source archive link or special file")
    if member.size < 0 or member.size > MAX_ARCHIVE_BYTES:
        raise ValueError("Source archive member exceeds the size limit")
    return relative


def extract_source(archive: Path, destination: Path) -> None:
    """Validate all entries before writing; never extract links or special files."""
    if file_sha256(archive) != SOURCE_SHA256:
        raise ValueError("Source archive SHA-256 mismatch")
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        paths = [archive_member_path(member) for member in members]
        if len(set(paths)) != len(paths):
            raise ValueError("Duplicate source archive member")
        if sum(member.size for member in members) > MAX_SOURCE_BYTES:
            raise ValueError("Source archive expands beyond the size limit")
        destination.mkdir()
        for member, relative in zip(members, paths, strict=True):
            if not relative or member.issym():
                continue
            target = destination / relative
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            data = source.extractfile(member)
            if data is None:
                raise ValueError("Source archive member has no contents")
            with data, target.open("xb") as output:
                shutil.copyfileobj(data, output)


def expected_backport_contents(source: Path) -> dict[str, bytes]:
    """Describe the entire allowed change, independent of the patch executable."""
    result = {}
    for name in PIN_FILES:
        contents = (source / name).read_bytes()
        if contents.count(b"Pillow==12.3.0") != 1:
            raise ValueError(f"Unexpected upstream Pillow pin: {name}")
        result[name] = contents.replace(b"Pillow==12.3.0", b"Pillow==13.0.0")
    project = tomllib.loads((source / "pyproject.toml").read_text())
    if (project["project"]["name"] != "homeassistant"
            or project["project"]["version"] != BASE_VERSION
            or project["build-system"] != {
                "requires": [UPSTREAM_BUILD_BACKEND], "build-backend": "setuptools.build_meta",
            }):
        raise ValueError("Unexpected upstream project identity or build backend")
    if result["pyproject.toml"].count(UPSTREAM_BUILD_BACKEND.encode()) != 1:
        raise ValueError("Unexpected upstream build backend declaration")
    result["pyproject.toml"] = result["pyproject.toml"].replace(
        UPSTREAM_BUILD_BACKEND.encode(), BUILD_BACKEND.encode(),
    )
    old_version = f'version = "{BASE_VERSION}"'.encode()
    if result["pyproject.toml"].count(old_version) != 1:
        raise ValueError("Unexpected upstream project version declaration")
    result["pyproject.toml"] = result["pyproject.toml"].replace(
        old_version, f'version = "{LOCAL_VERSION}"'.encode(),
    )
    constants = (source / "homeassistant/const.py").read_bytes()
    old_patch = b'PATCH_VERSION: Final = "4"\n'
    if constants.count(old_patch) != 1 or b"SECURITY_BACKPORT" in constants:
        raise ValueError("Unexpected upstream runtime version declaration")
    # HA's AwesomeVersion treats a +local runtime string as SEMVER, not CALVER.
    # Preserve runtime calendar-version comparisons; distribution metadata and
    # the explicit marker below identify this custom build without ambiguity.
    result["homeassistant/const.py"] = constants.replace(
        old_patch, old_patch + f'SECURITY_BACKPORT: Final = "{SECURITY_BACKPORT}"\n'.encode(),
    )
    return result


def build_environment() -> dict[str, str]:
    """Pass build necessities, never CI tokens or caller package-index overrides."""
    allowed = {
        "PATH", "HOME", "SYSTEMROOT", "WINDIR", "TMPDIR", "TMP", "TEMP",
        "LANG", "LC_ALL", "LC_CTYPE", "SSL_CERT_FILE", "SSL_CERT_DIR",
        "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY",
        "https_proxy", "http_proxy", "all_proxy", "no_proxy",
    }
    environment = {key: value for key, value in os.environ.items() if key in allowed}
    environment.update({
        "SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH,
        "PIP_CONFIG_FILE": os.devnull,
        "PIP_INDEX_URL": "https://pypi.org/simple",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONNOUSERSITE": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
    })
    return environment


def apply_backport(source: Path, patch: bytes, log) -> dict[str, bytes]:
    """Apply the verified patch and assert every changed byte has the intended meaning."""
    expected = expected_backport_contents(source)
    patch_path = source.parent / "verified-backport.patch"
    patch_path.write_bytes(patch)
    git = shutil.which("git")
    if git is None:
        raise ValueError("Git is required to apply the verified patch")
    for options in (["--check"], []):
        subprocess.run(
            [git, "apply", *options, "--whitespace=error-all", str(patch_path)],
            cwd=source, env=build_environment(), check=True, stdout=log, stderr=subprocess.STDOUT,
        )
    if any((source / name).read_bytes() != contents for name, contents in expected.items()):
        raise ValueError("Backport changed more than the allowed pins, backend and build identity")
    return expected


def runtime_constants(contents: bytes) -> dict[str, object]:
    """Inspect literal version fields without importing executable upstream code."""
    result = {}
    names = {"MAJOR_VERSION", "MINOR_VERSION", "PATCH_VERSION", "SECURITY_BACKPORT"}
    for node in ast.parse(contents).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id in names:
            result[node.target.id] = ast.literal_eval(node.value)
    return result


def verify_wheel(wheel: Path, expected: dict[str, bytes]) -> dict:
    """Check the built artifact, including all runtime dependency pins and its identity."""
    if wheel.name != f"homeassistant-{LOCAL_VERSION}-py3-none-any.whl":
        raise ValueError("Unexpected security wheel filename")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names):
            raise ValueError("Duplicate security wheel member")
        metadata = BytesParser().parsebytes(
            archive.read(f"homeassistant-{LOCAL_VERSION}.dist-info/METADATA")
        )
        if metadata["Name"] != "homeassistant" or metadata["Version"] != LOCAL_VERSION:
            raise ValueError("Security wheel distribution identity mismatch")
        pillow = [item for item in metadata.get_all("Requires-Dist", [])
                  if re.match(r"(?i)^pillow\b", item)]
        if pillow != [f"Pillow=={PILLOW_VERSION}"]:
            raise ValueError("Security wheel metadata Pillow requirement mismatch")
        for name, contents in expected.items():
            if name.startswith("homeassistant/") and archive.read(name) != contents:
                raise ValueError(f"Security wheel source mismatch: {name}")
        constants = runtime_constants(archive.read("homeassistant/const.py"))
        if constants != {
            "MAJOR_VERSION": 2026, "MINOR_VERSION": 10, "PATCH_VERSION": "4",
            "SECURITY_BACKPORT": SECURITY_BACKPORT,
        }:
            raise ValueError("Security wheel runtime version or backport marker mismatch")
    return {
        "wheel_filename": wheel.name,
        "wheel_sha256": file_sha256(wheel),
        "wheel_size_bytes": wheel.stat().st_size,
    }


def build_security_runtime(output_dir: Path) -> Path:
    """Produce one verified wheel and provenance, refusing existing destinations."""
    if output_dir.exists() or output_dir.is_symlink():
        raise ValueError("Output directory must be a fresh path")
    if sys.version_info < (3, 14, 2):
        raise ValueError("The security runtime requires Python >=3.14.2")
    if version("build") != "1.6.1":
        raise ValueError(f"Install the pinned build frontend: {BUILD_FRONTEND}")
    verified_patch(
        PATCH_DIRECTORY / "homeassistant-upstream-pillow13.patch", UPSTREAM_PATCH_SHA256, set(PIN_FILES),
    )
    patch = verified_patch(
        PATCH_DIRECTORY / "homeassistant-2026.10.4-pillow13.patch",
        BACKPORT_PATCH_SHA256, set(PIN_FILES) | set(IDENTITY_FILES),
    )
    output_dir.mkdir(parents=True)
    output_dir = output_dir.resolve()
    with tempfile.TemporaryDirectory(prefix="ovo-ha-security-build-") as temporary:
        work = Path(temporary)
        archive = work / "source.tar.gz"
        source = work / "source"
        wheels = work / "wheels"
        download_source(archive)
        extract_source(archive, source)
        with (output_dir / "build.log").open("x") as log:
            expected = apply_backport(source, patch, log)
            subprocess.run(
                [sys.executable, "-I", "-m", "build", "--wheel", "--outdir", str(wheels), str(source)],
                cwd=work, env=build_environment(), check=True, stdout=log, stderr=subprocess.STDOUT,
            )
        built = list(wheels.iterdir())
        if len(built) != 1 or built[0].suffix != ".whl" or built[0].is_symlink():
            raise ValueError("Build must produce exactly one regular wheel")
        artifact = verify_wheel(built[0], expected)
        provenance = {
            "schema_version": 1,
            "purpose": "OVO CI security runtime; not an official Home Assistant release",
            "upstream_repository": "https://github.com/home-assistant/core",
            "base_version": BASE_VERSION,
            "base_commit": BASE_COMMIT,
            "source_url": SOURCE_URL,
            "source_sha256": SOURCE_SHA256,
            "source_date_epoch": SOURCE_DATE_EPOCH,
            "upstream_pillow13_commit": UPSTREAM_PILLOW_COMMIT,
            "upstream_patch_sha256": UPSTREAM_PATCH_SHA256,
            "backport_patch_sha256": BACKPORT_PATCH_SHA256,
            "local_version": LOCAL_VERSION,
            "runtime_version": BASE_VERSION,
            "security_backport": SECURITY_BACKPORT,
            "pillow_version": PILLOW_VERSION,
            "pin_files": list(PIN_FILES),
            "identity_files": list(IDENTITY_FILES),
            "omitted_nonpackage_symlinks": list(OMITTED_NONPACKAGE_SYMLINKS),
            "build_frontend": BUILD_FRONTEND,
            "upstream_build_backend": UPSTREAM_BUILD_BACKEND,
            "build_backend": BUILD_BACKEND,
            "build_backend_advisory": BUILD_BACKEND_ADVISORY,
            "build_backend_fix_commit": BUILD_BACKEND_FIX_COMMIT,
            "python_version": platform.python_version(),
            **artifact,
        }
        wheel = output_dir / built[0].name
        with built[0].open("rb") as src, wheel.open("xb") as dst:
            shutil.copyfileobj(src, dst)
        with (output_dir / "provenance.json").open("x") as file:
            json.dump(provenance, file, indent=2, sort_keys=True)
            file.write("\n")
    print(f"Built verified custom runtime: {wheel}")
    print(f"Provenance: {output_dir / 'provenance.json'}")
    return wheel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    build_security_runtime(arguments.output_dir)


if __name__ == "__main__":
    main()
