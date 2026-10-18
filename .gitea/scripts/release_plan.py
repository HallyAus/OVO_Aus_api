"""Read-only local release preflight; print a manual plan, never publish or read tokens."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

REPO = "HallyAus/OVO_Aus_api"


def command(*args: str) -> str:
    return subprocess.check_output(list(args), text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path, help="Downloaded private Gitea artifact directory")
    parser.add_argument("--reviewed-run-url", required=True, help="Exact successful Gitea run inspected by the operator")
    parser.add_argument("--reviewed-hacs-result", required=True, help="Official HACS run inspected by the operator")
    parser.add_argument("--reviewed-hacs-sha", required=True, help="Exact source SHA shown by the successful HACS run")
    parser.add_argument("--notes-file", required=True, type=Path)
    args = parser.parse_args()
    proof = json.loads((args.candidate / "provenance.json").read_text(encoding="utf-8"))
    sha = proof["source_sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", proof["version"]):
        raise SystemExit("Invalid source or stable version")
    run_url = f"http://192.168.1.130:3000/hallyaus/OVO_Aus_api/actions/runs/{proof['run_id']}"
    if args.reviewed_run_url != run_url or proof["run_id"] is None:
        raise SystemExit("Operator review must name the originating Gitea run")
    if (proof.get("repository") != "hallyaus/OVO_Aus_api"
            or proof.get("source_server") != "http://192.168.1.130:3000"
            or proof.get("published") is not False
            or proof.get("posix_paths_verified") is not True
            or proof.get("gitea_gates") != {name: "success" for name in ("unit", "runtime", "hassfest")}):
        raise SystemExit("Candidate has not passed every required Gitea gate")
    if args.reviewed_hacs_sha != sha or not re.fullmatch(
            r"http://192\.168\.1\.130:3000/hallyaus/OVO_Aus_api/actions/runs/[0-9]+(?:/jobs/[0-9]+)?",
            args.reviewed_hacs_result):
        raise SystemExit("HACS evidence must explicitly identify this exact source SHA")
    if not args.notes_file.is_file() or not args.notes_file.read_text(encoding="utf-8").strip():
        raise SystemExit("Review release notes, including existing referral/support text")
    archive = args.candidate / "ovo_energy_au.zip"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != proof["archive_sha256"]:
        raise SystemExit("Downloaded candidate checksum differs")
    if command("git", "rev-parse", "HEAD") != sha:
        raise SystemExit("Local source must match the verified candidate")
    expected = {}
    entries = subprocess.check_output(["git", "ls-tree", "-rz", sha, "--", "custom_components/ovo_energy_au/"])
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        meta, path = entry.split(b"\t", 1)
        mode, kind, oid = meta.decode().split()
        if mode not in ("100644", "100755") or kind != "blob":
            raise SystemExit("Unexpected non-file integration source")
        name = path.decode().removeprefix("custom_components/")
        expected[name] = subprocess.check_output(["git", "cat-file", "blob", oid])
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() or sorted(zipped.namelist()) != sorted(expected):
            raise SystemExit("Candidate member set differs from the exact source")
        if any(zipped.read(name) != data for name, data in expected.items()):
            raise SystemExit("Candidate contents differ from the exact source")
    user = json.loads(command("gh", "api", "user"))
    repo = json.loads(command("gh", "api", f"repos/{REPO}"))
    actions = json.loads(command("gh", "api", f"repos/{REPO}/actions/permissions"))
    if user.get("login") != "HallyAus" or user.get("id") != 37143514:
        raise SystemExit("Expected Daniel's personal GitHub account")
    if repo.get("id") != 1137905255 or repo.get("private") is not False or actions.get("enabled") is not False:
        raise SystemExit("Public compatibility repository and disabled Actions required")
    tag = "v" + proof["version"]
    for remote in ("origin", "github"):
        refs = command("git", "ls-remote", remote, f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}")
        rows = [line.split() for line in refs.splitlines() if line]
        resolved = next((oid for oid, name in rows if name.endswith("^{}")), rows[0][0] if rows else None)
        if resolved != sha:
            raise SystemExit("Existing primary and recovery tags must both resolve to the tested source; this tool never creates tags")
    releases = json.loads(command("gh", "api", f"repos/{REPO}/releases?per_page=100"))
    if any(release.get("tag_name") == tag for release in releases):
        raise SystemExit("Release already exists; never overwrite or duplicate its assets")
    print(json.dumps({
        "status": "manual operator review still required; no publication performed",
        "source_sha": sha, "run_url": run_url, "hacs_result": args.reviewed_hacs_result,
        "draft_command": ["gh", "release", "create", tag, "--repo", REPO, "--draft", "--verify-tag",
                          "--target", sha, "--notes-file", str(args.notes_file.resolve()), str(archive.resolve())],
        "after_draft": "Download the draft asset and compare SHA256/members; verify tag/source again. Only then separately authorize public publication.",
        "publish_command": ["gh", "release", "edit", tag, "--repo", REPO, "--draft=false", "--latest"],
        "github_hosted_compute": False,
    }, indent=2))


if __name__ == "__main__":
    main()
