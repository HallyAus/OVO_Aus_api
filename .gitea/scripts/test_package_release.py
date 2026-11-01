"""Offline packaging regressions; never call OVO, HA, or a release provider."""
import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("package_release", Path(__file__).with_name("package_release.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PackageTests(unittest.TestCase):
    def test_posix_reproducible_roundtrip(self):
        files = {"ovo_energy_au/sensors/test.py": b"synthetic\n", "ovo_energy_au/manifest.json": b"{}"}
        with tempfile.TemporaryDirectory() as root:
            first, second = Path(root) / "a.zip", Path(root) / "b.zip"
            module.package(files, first)
            module.package(dict(reversed(list(files.items()))), second)
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(), hashlib.sha256(second.read_bytes()).digest())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.read("ovo_energy_au/sensors/test.py"), b"synthetic\n")
                self.assertTrue(all("\\" not in name for name in archive.namelist()))
                self.assertTrue(all(member.create_system == 3 and member.external_attr >> 16 == 0o100644
                                    for member in archive.infolist()))

    def test_refuse_traversal_generated_windows_and_wrong_root(self):
        for name in ("ovo_energy_au/../secret", "ovo_energy_au\\sensor.py", "/ovo_energy_au/x",
                     "ovo_energy_au/__pycache__/x.pyc", "ovo_energy_au/x.pyc", "other/x"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as root, self.assertRaises(ValueError):
                module.package({name: b"synthetic"}, Path(root) / "a.zip")

    def test_refuse_empty_and_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "a.zip"
            with self.assertRaises(ValueError):
                module.package({}, target)
            target.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                module.package({"ovo_energy_au/x": b"synthetic"}, target)
            self.assertEqual(target.read_bytes(), b"existing")

    def test_refuses_ambiguous_archive_names_before_creating_output(self):
        for name in ("ovo_energy_au/a\x00.py", "ovo_energy_au//x", "ovo_energy_au/./x",
                     "ovo_energy_au/x/", "ovo_energy_au/", "ovo_energy_au/x:stream"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as root:
                target = Path(root) / "candidate.zip"
                with self.assertRaises(ValueError):
                    module.package({name: b"synthetic"}, target)
                self.assertFalse(target.exists())

    def test_provenance_never_overwrites_existing_file_or_follows_symlink(self):
        sha = "a" * 40
        manifest = json.dumps({"version": "9.9.9"}).encode()

        def git(*args):
            if args == ("rev-parse", "HEAD"):
                return sha.encode()
            if args[0] == "status":
                return b""
            if args == ("show", f"{sha}:{module.PREFIX}manifest.json"):
                return manifest
            if args == ("show", f"{sha}:pyproject.toml"):
                return b'[project]\nversion = "9.9.9"\n'
            if args[0] == "ls-tree":
                return (f"100644 blob {'b' * 40}\t{module.PREFIX}manifest.json\0").encode()
            if args[0] == "cat-file":
                return manifest
            if args == ("rev-parse", "HEAD^{tree}"):
                return b"c" * 40
            self.fail(f"Unexpected git operation: {args}")

        for symlink in (False, True):
            with self.subTest(symlink=symlink), tempfile.TemporaryDirectory() as root:
                directory = Path(root)
                victim = directory / "existing.txt"
                victim.write_bytes(b"must remain unchanged")
                output = directory / "dist"
                output.mkdir()
                receipt = output / "provenance.json"
                if symlink:
                    receipt.symlink_to(victim)
                else:
                    receipt.write_bytes(b"must remain unchanged")
                with patch("sys.argv", ["package_release.py", "--output", str(output)]), \
                        patch.dict(os.environ, {"GITHUB_SHA": sha}, clear=True), \
                        patch.object(module, "git", side_effect=git), patch("builtins.print"), \
                        self.assertRaises(FileExistsError):
                    module.main()
                self.assertEqual(victim.read_bytes(), b"must remain unchanged")
                self.assertEqual(receipt.read_bytes(), b"must remain unchanged")


if __name__ == "__main__":
    unittest.main()
