"""Secret-using workflows stay least privilege and pin third-party actions."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHA_PIN = re.compile(r"@[0-9a-f]{40}(?:\s|$)")
VERSION_COMMENT = re.compile(r"#\s*v\d")
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)")
TOP_LEVEL_PERMISSIONS = re.compile(r"^permissions:[ \t]*(\{\})?[ \t]*$", re.M)
WRITE_GRANT = re.compile(r":\s*write\b")


def _workflow_files() -> list[Path]:
    roots = (ROOT / ".github" / "workflows", ROOT / ".gitea" / "workflows")
    return [path for root in roots for path in sorted(root.glob("*.yml"))]


def _secret_workflows() -> list[tuple[Path, str]]:
    found = []
    for path in _workflow_files():
        text = path.read_text()
        if "secrets." in text:
            found.append((path, text))
    return found


def _is_actions_reference(ref: str) -> bool:
    if ref.startswith("actions/"):
        return True
    return ref.startswith("https://github.com/actions/")


def test_dependabot_auto_merge_accepts_only_semver_patch_merge_commits():
    text = (ROOT / ".github/workflows/dependabot-auto-merge.yml").read_text()
    before_jobs = text.split("\njobs:", 1)[0]
    assert "permissions: {}" in before_jobs
    assert "github.event.pull_request.user.login == 'dependabot[bot]'" in text
    assert "github.repository == 'HallyAus/OVO_Aus_api'" in text
    assert "steps.metadata.outputs.update-type == 'version-update:semver-patch'" in text
    assert 'gh pr merge --auto --merge "$PR_URL"' in text
    assert "--squash" not in text
    assert "--rebase" not in text
    assert (
        "dependabot/fetch-metadata@25dd0e34f4fe68f24cc83900b1fe3fe149efef98 # v3.1.0"
        in text
    )
    assert "actions/checkout" not in text
    assert "contents: write" in text
    assert "pull-requests: write" in text
    for forbidden in (
        "actions: write",
        "id-token:",
        "packages:",
        "security-events:",
        "write-all",
        "checks: write",
    ):
        assert forbidden not in text


def test_secret_workflows_declare_top_level_least_privilege_permissions():
    workflows = _secret_workflows()
    assert {path.name for path, _ in workflows} == {
        "dependabot-auto-merge.yml",
        "release.yml",
        "ci.yml",
        "hacs-public-validation.yml",
    }
    for path, text in workflows:
        before_jobs = text.split("\njobs:", 1)[0]
        match = TOP_LEVEL_PERMISSIONS.search(before_jobs)
        assert match, path
        if match.group(1) == "{}":
            continue
        block = before_jobs[match.end():]
        next_key = re.search(r"^[A-Za-z0-9_-]+:", block, re.M)
        block = block[: next_key.start()] if next_key else block
        assert WRITE_GRANT.search(block) is None, path


def test_secret_workflows_pin_non_actions_third_party_actions():
    seen = False
    for path, text in _secret_workflows():
        for line in text.splitlines():
            match = USES.search(line)
            if match is None:
                continue
            ref = match.group(1)
            if ref.startswith("./") or _is_actions_reference(ref):
                continue
            seen = True
            assert SHA_PIN.search(ref), (path, ref)
            assert VERSION_COMMENT.search(line), (path, line)
    assert seen
