"""Synthetic release safety checks; all Git/provider calls are mocked."""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location("release_plan", Path(__file__).with_name("release_plan.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SHA = "a" * 40


class ReleasePlanTests(unittest.TestCase):
    def check(self, *, gate="success", tamper=False, identity="HallyAus", enabled=False,
              release=False, remote_sha=SHA, expected_error=None):
        calls = []
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            archive = directory / "ovo_energy_au.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("ovo_energy_au/manifest.json", b"synthetic")
            proof = {
                "repository": "hallyaus/OVO_Aus_api", "source_server": "http://192.168.1.130:3000",
                "source_sha": SHA, "version": "9.9.9", "run_id": "123", "published": False,
                "posix_paths_verified": True,
                "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "gitea_gates": {name: gate for name in ("unit", "runtime", "hassfest")},
            }
            (directory / "provenance.json").write_text(json.dumps(proof), encoding="utf-8")
            notes = directory / "notes.md"
            notes.write_text("Reviewed synthetic notes", encoding="utf-8")
            if tamper:
                archive.write_bytes(b"tampered")

            def read(*args):
                calls.append(args)
                if args == ("git", "rev-parse", "HEAD"):
                    return SHA
                if args[:2] == ("git", "ls-remote"):
                    return f"{remote_sha}\trefs/tags/v9.9.9"
                if args[:2] != ("gh", "api"):
                    self.fail(f"Unexpected operation: {args}")
                endpoint = args[2]
                if endpoint == "user":
                    return json.dumps({"login": identity, "id": 37143514})
                if endpoint.endswith("actions/permissions"):
                    return json.dumps({"enabled": enabled})
                if endpoint.endswith("releases?per_page=100"):
                    return json.dumps([{"tag_name": "v9.9.9"}] if release else [])
                return json.dumps({"id": 1137905255, "private": False})

            def git_bytes(args, **kwargs):
                if args[:2] == ["git", "ls-tree"]:
                    return b"100644 blob bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\tcustom_components/ovo_energy_au/manifest.json\0"
                if args[:3] == ["git", "cat-file", "blob"]:
                    return b"synthetic"
                self.fail(f"Unexpected operation: {args}")

            argv = ["release_plan.py", "--candidate", root, "--reviewed-run-url",
                    "http://192.168.1.130:3000/hallyaus/OVO_Aus_api/actions/runs/123",
                    "--reviewed-hacs-result", "http://192.168.1.130:3000/hallyaus/OVO_Aus_api/actions/runs/124",
                    "--reviewed-hacs-sha", SHA,
                    "--notes-file", str(notes)]
            with patch("sys.argv", argv), patch.object(module, "command", side_effect=read), \
                    patch.object(module.subprocess, "check_output", side_effect=git_bytes):
                if expected_error:
                    with self.assertRaisesRegex(SystemExit, expected_error):
                        module.main()
                else:
                    output = io.StringIO()
                    with redirect_stdout(output):
                        module.main()
                    plan = json.loads(output.getvalue())
                    self.assertIn("--verify-tag", plan["draft_command"])
                    self.assertIn("--draft", plan["draft_command"])
                    self.assertFalse(plan["github_hosted_compute"])
            # Only API GETs and Git ref reads were allowed through the mock.
            self.assertFalse(any("release" in args[:2] or "--method" in args for args in calls))

    def test_reviewed_candidate_only_prints_a_manual_plan(self):
        self.check()

    def test_refuses_unverified_gate_before_provider_access(self):
        self.check(gate="unverified", expected_error="every required Gitea gate")

    def test_refuses_tampered_asset(self):
        self.check(tamper=True, expected_error="checksum differs")

    def test_refuses_wrong_identity(self):
        self.check(identity="wrong", expected_error="personal GitHub account")

    def test_refuses_enabled_github_actions(self):
        self.check(enabled=True, expected_error="disabled Actions required")

    def test_refuses_existing_release(self):
        self.check(release=True, expected_error="never overwrite")

    def test_refuses_moved_or_missing_tag(self):
        self.check(remote_sha="b" * 40, expected_error="tags must both resolve")


if __name__ == "__main__":
    unittest.main()
