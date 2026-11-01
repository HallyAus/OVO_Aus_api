"""Build an immutable POSIX release ZIP only from the verified Git commit."""

from __future__ import annotations

import os
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

PREFIX = "custom_components/ovo_energy_au/"


def _git(*arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments])


def build_archive(sha: str, output: Path) -> None:
    """Reject source drift, symlinks, unsafe member paths and existing artifacts."""
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or _git("rev-parse", "HEAD").decode().strip() != sha:
        raise ValueError("Checkout differs from the verified source commit")
    if _git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Tracked source must be clean")
    files = {}
    for entry in _git("ls-tree", "-rz", sha, "--", PREFIX).split(b"\0"):
        if not entry:
            continue
        metadata, source_path = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        if mode not in ("100644", "100755") or kind != "blob":
            raise ValueError("Only regular tracked integration files may be released")
        name = source_path.decode().removeprefix("custom_components/")
        path = PurePosixPath(name)
        if (path.is_absolute() or path.as_posix() != name or ".." in path.parts
                or "\\" in name or ":" in name or not name.startswith("ovo_energy_au/")
                or any(ord(character) < 32 or ord(character) == 127 for character in name)
                or "__pycache__" in path.parts or name.endswith((".pyc", ".pyo"))):
            raise ValueError("Unsafe or generated release archive member")
        files[name] = _git("cat-file", "blob", oid)
    if not files:
        raise ValueError("An empty integration cannot be released")
    # Exclusive creation prevents overwriting an artifact or following a symlink.
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(files.items()):
            member = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            member.create_system = 3
            member.external_attr = 0o100644 << 16
            member.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(member, content, compresslevel=9)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or sorted(archive.namelist()) != sorted(files):
            raise ValueError("Release archive verification failed")
        if any(archive.read(name) != content for name, content in files.items()):
            raise ValueError("Release archive differs from verified source")


if __name__ == "__main__":
    build_archive(os.environ["GITHUB_SHA"], Path("ovo_energy_au.zip"))
