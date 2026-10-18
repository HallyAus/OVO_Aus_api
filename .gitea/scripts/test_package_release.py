"""Offline packaging regressions; never call OVO, HA, or a release provider."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

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

    def test_refuse_traversal_generated_windows_and_wrong_root(self):
        for name in ("ovo_energy_au/../secret", "ovo_energy_au\\sensor.py", "/ovo_energy_au/x",
                     "ovo_energy_au/__pycache__/x.pyc", "ovo_energy_au/x.pyc", "other/x"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as root:
                with self.assertRaises(ValueError):
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


if __name__ == "__main__":
    unittest.main()
