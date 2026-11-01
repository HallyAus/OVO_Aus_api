"""Release provenance and security gates must fail closed."""

import importlib.util
import subprocess
import zipfile
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "verify_github_release", Path(__file__).resolve().parents[1] / "scripts/verify_github_release.py"
)
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)
_archive_spec = importlib.util.spec_from_file_location(
    "package_github_release", Path(__file__).resolve().parents[1] / "scripts/package_github_release.py"
)
packaging = importlib.util.module_from_spec(_archive_spec)
_archive_spec.loader.exec_module(packaging)

SOURCE_SHA = "a" * 40


def _run(**overrides):
    return {
        "id": 101, "run_number": 1, "run_attempt": 1,
        "head_sha": SOURCE_SHA, "event": "push", "head_branch": "main",
        "status": "completed", "conclusion": "success", **overrides,
    }


def _jobs():
    return [{"name": name, "status": "completed", "conclusion": "success"}
            for name in release.REQUIRED_CI_JOBS]


def test_release_refuses_existing_tag_for_a_different_commit():
    with pytest.raises(ValueError, match="different source"):
        release.verify_versions("v4.10.2", "4.10.2", "4.10.2", SOURCE_SHA, "b" * 40)


@pytest.mark.parametrize("tag", ["v4.10.2-rc1", "--version", "v4.10.2;echo", "refs/tags/v4.10.2"])
def test_release_rejects_untrusted_or_prerelease_tag_input(tag):
    with pytest.raises(ValueError, match="stable semantic"):
        release.verify_versions(tag, "4.10.2", "4.10.2", SOURCE_SHA, None)


def test_release_refuses_mismatched_package_version():
    with pytest.raises(ValueError, match="source version"):
        release.verify_versions("v4.10.2", "4.10.2", "4.10.1", SOURCE_SHA, None)


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", None])
def test_newer_unsuccessful_ci_cannot_be_hidden_by_old_success(conclusion):
    with pytest.raises(ValueError, match="Latest CI"):
        release.select_ci_run([_run(), _run(id=102, run_number=2, conclusion=conclusion)], SOURCE_SHA)


@pytest.mark.parametrize("overrides", [
    {"event": "pull_request"}, {"head_branch": "feature"}, {"head_sha": "b" * 40},
])
def test_release_requires_success_on_its_own_main_branch_commit(overrides):
    with pytest.raises(ValueError, match="main-branch CI"):
        release.select_ci_run([_run(**overrides)], SOURCE_SHA)


@pytest.mark.parametrize("conclusion", ["skipped", "failure", "cancelled", None])
def test_security_job_must_explicitly_succeed(conclusion):
    jobs = _jobs()
    next(job for job in jobs if job["name"] == "Home Assistant dependency security")["conclusion"] = conclusion
    with pytest.raises(ValueError, match="Required CI gate"):
        release.verify_jobs(jobs)


def test_successful_workflow_missing_security_job_is_rejected():
    jobs = [job for job in _jobs() if job["name"] != "Home Assistant dependency security"]
    with pytest.raises(ValueError, match="Required CI gate"):
        release.verify_jobs(jobs)


def test_successful_exact_source_and_all_security_jobs_are_accepted():
    release.verify_versions("v4.10.2", "4.10.2", "4.10.2", SOURCE_SHA, SOURCE_SHA)
    assert release.select_ci_run([_run()], SOURCE_SHA) == 101
    release.verify_jobs(_jobs())


def _git(*arguments, input=None):
    return subprocess.check_output(["git", *arguments], input=input).decode().strip()


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _git("init", "-q")
    _git("config", "user.name", "Fixture")
    _git("config", "user.email", "fixture@example.invalid")
    integration = tmp_path / "custom_components/ovo_energy_au"
    integration.mkdir(parents=True)
    (integration / "manifest.json").write_text("{}\n")
    _git("add", "custom_components")
    _git("commit", "-qm", "fixture")
    return tmp_path, integration, _git("rev-parse", "HEAD")


@pytest.mark.parametrize("object_type", ["blob", "tree"])
def test_real_existing_tag_must_resolve_to_a_commit(repository, object_type):
    oid = (_git("hash-object", "-w", "--stdin", input=b"fixture")
           if object_type == "blob" else _git("mktree", input=b""))
    _git("update-ref", "refs/tags/v4.10.2", oid)
    with pytest.raises(ValueError, match="does not point to a commit"):
        release.existing_tag_target("v4.10.2")


def test_missing_tag_and_matching_commit_tag_are_distinct(repository):
    _, _, sha = repository
    assert release.existing_tag_target("v4.10.2") is None
    _git("tag", "v4.10.2", sha)
    assert release.existing_tag_target("v4.10.2") == sha


def test_archive_excludes_untracked_and_generated_working_files(repository):
    root, integration, sha = repository
    (integration / "untracked.txt").write_text("must not ship")
    (integration / "__pycache__").mkdir()
    (integration / "__pycache__/test.pyc").write_bytes(b"must not ship")
    output = root / "release.zip"
    packaging.build_archive(sha, output)
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ["ovo_energy_au/manifest.json"]
        assert archive.read(archive.namelist()[0]) == b"{}\n"
        assert archive.infolist()[0].external_attr >> 16 == 0o100644


def test_archive_rejects_tracked_symlinks_without_reading_target(repository):
    root, integration, _ = repository
    target = root / "private-fixture.txt"
    target.write_text("must not ship")
    (integration / "linked.txt").symlink_to(target)
    _git("add", "custom_components")
    _git("commit", "-qm", "symlink fixture")
    with pytest.raises(ValueError, match="Only regular tracked"):
        packaging.build_archive(_git("rev-parse", "HEAD"), root / "release.zip")
    assert not (root / "release.zip").exists()


def test_archive_refuses_changed_source_and_artifact_overwrite(repository):
    root, integration, sha = repository
    output = root / "release.zip"
    packaging.build_archive(sha, output)
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        packaging.build_archive(sha, output)
    assert output.read_bytes() == original
    (integration / "manifest.json").write_text('{"changed":true}\n')
    with pytest.raises(ValueError, match="Tracked source must be clean"):
        packaging.build_archive(sha, root / "changed.zip")
