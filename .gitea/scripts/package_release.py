"""Build a reproducible, non-publishing release candidate from tracked Git blobs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tomllib
import zipfile

PREFIX = "custom_components/ovo_energy_au/"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def package(files: dict[str, bytes], output: Path) -> None:
    if not files:
        raise ValueError("An empty integration cannot be packaged")
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            path = PurePosixPath(name)
            if ("\\" in name or path.is_absolute() or ".." in path.parts
                    or not name.startswith("ovo_energy_au/")
                    or "__pycache__" in path.parts or name.endswith((".pyc", ".pyo"))):
                raise ValueError("Unsafe or generated archive member")
            member = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            member.create_system = 3
            member.external_attr = 0o100644 << 16
            member.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(member, data, compresslevel=9)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or sorted(archive.namelist()) != sorted(files):
            raise ValueError("Archive verification failed")
        for name, data in files.items():
            if archive.read(name) != data:
                raise ValueError("Archive differs from the selected source")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    sha = git("rev-parse", "HEAD").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise SystemExit("Expected an exact Git source commit")
    if os.getenv("GITHUB_SHA", sha) != sha:
        raise SystemExit("Checkout differs from the workflow source")
    # Do not silently release a different working tree, including staged changes.
    if git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("Tracked source must be clean")
    manifest = json.loads(git("show", f"{sha}:{PREFIX}manifest.json"))
    project = tomllib.loads(git("show", f"{sha}:pyproject.toml").decode())
    version = manifest["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) or project["project"]["version"] != version:
        raise SystemExit("Stable manifest/project versions must agree")
    files = {}
    for entry in git("ls-tree", "-rz", sha, "--", PREFIX).split(b"\0"):
        if not entry:
            continue
        metadata, name_bytes = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        if mode not in ("100644", "100755") or kind != "blob":
            raise SystemExit("Only regular tracked integration files are allowed")
        name = name_bytes.decode("utf-8")
        files[name.removeprefix("custom_components/")] = git("cat-file", "blob", oid)
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / "ovo_energy_au.zip"
    package(files, target)
    receipt = {
        "repository": "hallyaus/OVO_Aus_api", "source_server": "http://192.168.1.130:3000",
        "source_sha": sha, "source_tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
        "version": version, "archive": target.name, "members": len(files),
        "archive_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "run_id": os.getenv("GITHUB_RUN_ID"), "posix_paths_verified": True,
        "gitea_gates": {name: os.getenv(f"GATE_{name.upper()}", "unverified")
                        for name in ("unit", "runtime", "hassfest")},
        "hacs_external_validation": "unverified; required before public release",
        "published": False,
    }
    (args.output / "provenance.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
