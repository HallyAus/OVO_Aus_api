"""Offline refusal-path tests using local bare repositories only."""
import importlib.util
import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("recover_github", Path(__file__).with_name("recover_github.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
OK = {"unit": "success", "runtime": "success", "hassfest": "success", "candidate": "success"}


def run(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class RecoverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.remote = str(root / "recovery.git")
        self.work = root / "work"
        run(root, "init", "--bare", "-b", "main", self.remote)
        run(root, "init", "-b", "main", str(self.work))
        for key, val in (("user.name", "t"), ("user.email", "t@example.invalid")):
            run(self.work, "config", key, val)
        self.c1 = self.commit("one")
        run(self.work, "push", self.remote, "main")
        self.c2 = self.commit("two")
        self.cwd = os.getcwd()
        os.chdir(self.work)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def commit(self, name):
        (self.work / name).write_text(name)
        run(self.work, "add", name)
        run(self.work, "commit", "-m", name)
        return run(self.work, "rev-parse", "HEAD")

    def head(self):
        return run(self.work, "ls-remote", self.remote, "refs/heads/main").split()[0]

    def test_fast_forward_pushes_exact_sha(self):
        self.assertEqual(mod.recover(self.c2, OK, self.remote), "pushed")
        self.assertEqual(self.head(), self.c2)
        self.assertEqual(mod.recover(self.c2, OK, self.remote), "unchanged")

    def test_refuses_bad_gates_and_leaves_recovery_unchanged(self):
        for bad in ({}, {**OK, "runtime": "failure"}, {**OK, "hassfest": "skipped"},
                    {**OK, "unit": "cancelled"}, {**OK, "candidate": ""}):
            with self.assertRaises(mod.Refused):
                mod.recover(self.c2, bad, self.remote)
        self.assertEqual(self.head(), self.c1)

    def test_refuses_wrong_checkout_short_sha_and_missing_remote_ref(self):
        with self.assertRaises(mod.Refused):
            mod.recover(self.c1, OK, self.remote)
        with self.assertRaises(mod.Refused):
            mod.recover(self.c2[:7], OK, self.remote)
        empty = str(Path(self.tmp.name) / "empty.git")
        run(self.work, "init", "--bare", empty)
        with self.assertRaises(mod.Refused):
            mod.recover(self.c2, OK, empty)

    def test_refuses_divergent_recovery_and_preserves_it(self):
        run(self.work, "checkout", "-q", "-b", "other", self.c1)
        other = self.commit("other")
        run(self.work, "push", self.remote, "other:main")
        run(self.work, "checkout", "-q", "main")
        with self.assertRaises(mod.Refused):
            mod.recover(self.c2, OK, self.remote)
        self.assertEqual(self.head(), other)

    def test_does_not_push_tags_or_other_refs(self):
        run(self.work, "tag", "v9.9.9")
        mod.recover(self.c2, OK, self.remote)
        self.assertEqual(run(self.work, "ls-remote", "--tags", self.remote), "")

    def test_refuses_missing_named_gates_before_any_git_command(self):
        for missing in OK:
            with self.subTest(missing=missing), patch.object(mod, "git") as git:
                with self.assertRaises(mod.Refused):
                    mod.recover(self.c2, {k: v for k, v in OK.items() if k != missing}, self.remote)
                git.assert_not_called()

    def test_refuses_option_or_control_character_remote_before_git(self):
        for remote in ("", "--upload-pack=untrusted", "-oProxyCommand=untrusted", "repo\nother"):
            with self.subTest(remote=remote), patch.object(mod, "git") as git:
                with self.assertRaises(mod.Refused):
                    mod.recover(self.c2, OK, remote)
                git.assert_not_called()

    def test_ssh_command_quotes_paths_and_drops_plaintext_key_environment(self):
        root = Path(self.tmp.name)
        key = root / "deploy key; $(untrusted)"
        hosts = root / 'known hosts; "quoted"'
        key.write_text("synthetic fixture", encoding="utf-8")
        key.chmod(0o600)
        hosts.write_text("synthetic fixture", encoding="utf-8")
        environment = {
            "RECOVERY_GATES": json.dumps(OK), "RECOVERY_KEY_FILE": str(key),
            "RECOVERY_KNOWN_HOSTS": str(hosts), "GITHUB_SHA": self.c2,
            "RECOVERY_REMOTE": "git@github.com:HallyAus/OVO_Aus_api.git",
            "RECOVERY_DEPLOY_KEY": "synthetic-private-key", "SOURCE_TOKEN": "synthetic-token",
            "GH_TOKEN": "synthetic-token", "GITHUB_TOKEN": "synthetic-token",
            "GITEA_TOKEN": "synthetic-token", "INPUT_GITHUB_TOKEN": "synthetic-token",
            "GIT_ASKPASS": "/untrusted/helper", "SSH_ASKPASS": "/untrusted/helper",
        }
        with patch.dict(os.environ, environment, clear=True), patch.object(mod, "recover") as recover, \
                patch("builtins.print"):
            mod.main()
        env = recover.call_args.args[3]
        ssh_args = shlex.split(env["GIT_SSH_COMMAND"])
        self.assertEqual(ssh_args[ssh_args.index("-i") + 1], str(key))
        self.assertIn("UserKnownHostsFile=" + json.dumps(str(hosts)), ssh_args)
        for sensitive in ("RECOVERY_DEPLOY_KEY", "SOURCE_TOKEN", "GIT_ASKPASS", "SSH_ASKPASS",
                          "GH_TOKEN", "GITHUB_TOKEN", "GITEA_TOKEN", "INPUT_GITHUB_TOKEN"):
            self.assertNotIn(sensitive, env)

    def test_main_refuses_unexpected_remote_before_reading_key(self):
        with patch.dict(os.environ, {"RECOVERY_REMOTE": "git@unexpected.invalid:repo"}, clear=True), \
                patch.object(mod, "recover") as recover, self.assertRaises(mod.Refused):
            mod.main()
        recover.assert_not_called()


if __name__ == "__main__":
    unittest.main()
