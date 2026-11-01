"""Refuse publication without successful security gates for the exact source."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tomllib
from pathlib import Path

REQUIRED_CI_JOBS = frozenset({
    "lint", "test", "validate", "hacs",
    "Home Assistant runtime regressions",
    "Secrets, source security and package dependencies",
    "Home Assistant dependency security",
})


def verify_versions(tag: str, manifest: str, project: str, sha: str, tag_target: str | None) -> None:
    """Prevent mismatched source/archive/tag provenance."""
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("Expected a stable semantic release tag")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Expected an exact source commit")
    if manifest != tag[1:] or project != tag[1:]:
        raise ValueError("Release tag does not match the source version")
    if tag_target is not None and tag_target != sha:
        raise ValueError("Existing release tag points to a different source commit")


def select_ci_run(runs: list[dict], sha: str) -> int:
    """An older green run or a PR-only run cannot bypass the current main gate."""
    eligible = [
        run for run in runs
        if run.get("head_sha") == sha
        and run.get("event") == "push"
        and run.get("head_branch") == "main"
    ]
    if not eligible:
        raise ValueError("This exact commit needs a main-branch CI run")
    latest = max(eligible, key=lambda run: (run["run_number"], run.get("run_attempt", 1)))
    if latest.get("status") != "completed" or latest.get("conclusion") != "success":
        raise ValueError("Latest CI run for this exact commit is not successful")
    return int(latest["id"])


def verify_jobs(jobs: list[dict]) -> None:
    """Fail closed when a security or validation job is absent, skipped or failed."""
    for name in sorted(REQUIRED_CI_JOBS):
        matching = [job for job in jobs if job.get("name") == name]
        if (len(matching) != 1 or matching[0].get("status") != "completed"
                or matching[0].get("conclusion") != "success"):
            raise ValueError(f"Required CI gate did not pass: {name}")


def existing_tag_target(tag: str) -> str | None:
    """A tag pointing at a tree/blob is an invalid existing tag, not a missing one."""
    reference = f"refs/tags/{tag}"
    exists = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", reference], check=False,
    )
    if exists.returncode == 1:
        return None
    if exists.returncode != 0:
        raise ValueError("Unable to verify existing tag reference")
    target = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{reference}^{{commit}}"],
        check=False, capture_output=True, text=True,
    )
    if target.returncode != 0:
        raise ValueError("Existing release tag does not point to a commit")
    return target.stdout.strip()


def main() -> None:
    """Read trusted GitHub workflow metadata; never put its token in arguments."""
    tag = os.environ["RELEASE_TAG"]
    sha = os.environ["GITHUB_SHA"]
    repo = os.environ["GITHUB_REPOSITORY"]
    manifest = json.loads(Path("custom_components/ovo_energy_au/manifest.json").read_text())
    project = tomllib.loads(Path("pyproject.toml").read_text())
    verify_versions(tag, manifest["version"], project["project"]["version"], sha, None)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if head != sha:
        raise ValueError("Checkout does not match the workflow source commit")
    verify_versions(tag, manifest["version"], project["project"]["version"], sha,
                    existing_tag_target(tag))
    endpoint = f"repos/{repo}/actions/workflows/ci.yml/runs?head_sha={sha}&per_page=100"
    runs = json.loads(subprocess.check_output(["gh", "api", endpoint], text=True))["workflow_runs"]
    run_id = select_ci_run(runs, sha)
    jobs = json.loads(subprocess.check_output(
        ["gh", "api", f"repos/{repo}/actions/runs/{run_id}/jobs?filter=latest&per_page=100"], text=True,
    ))["jobs"]
    verify_jobs(jobs)
    print(f"Verified {tag}, source {sha}, and every required CI/security gate")


if __name__ == "__main__":
    main()
