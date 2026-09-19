#!/usr/bin/env python3

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class InstallPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name) / "home"
        self.home.mkdir()
        self.env = dict(os.environ, HOME=str(self.home))

    def tearDown(self):
        self.temp_dir.cleanup()

    def _run(self, script, *args):
        return subprocess.run(
            ["/bin/bash", str(PROJECT_ROOT / script), *args],
            cwd=PROJECT_ROOT,
            env=self.env,
            text=True,
            errors="replace",
            capture_output=True,
            timeout=5,
        )

    def test_install_plan_reports_all_side_effects_without_writing(self):
        result = self._run("install.sh", "--plan")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("只读，不执行", result.stdout)
        self.assertIn("真实额度", result.stdout)
        self.assertIn("LaunchAgent", result.stdout)
        self.assertFalse((self.home / "Library").exists())

    def test_uninstall_plan_reports_deletions_without_writing(self):
        result = self._run("uninstall.sh", "--plan")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("只读，不执行", result.stdout)
        self.assertIn("保留 rumps", result.stdout)
        self.assertFalse((self.home / "Library").exists())

    def test_unknown_argument_is_rejected_without_writing(self):
        for script in ("install.sh", "uninstall.sh"):
            with self.subTest(script=script):
                result = self._run(script, "--unknown")
                self.assertEqual(2, result.returncode)
        self.assertFalse((self.home / "Library").exists())

    def test_install_and_uninstall_refuse_symlinked_runtime_directory(self):
        support = self.home / "Library" / "Application Support"
        support.mkdir(parents=True)
        target = Path(self.temp_dir.name) / "external-target"
        target.mkdir()
        marker = target / "keep.txt"
        marker.write_text("fixture", encoding="utf-8")
        (support / "CodexQuotaBar").symlink_to(target, target_is_directory=True)

        install = self._run("install.sh")
        uninstall = self._run("uninstall.sh")
        self.assertNotEqual(0, install.returncode)
        self.assertNotEqual(0, uninstall.returncode)
        self.assertIn("符号链接", install.stderr)
        self.assertIn("符号链接", uninstall.stderr)
        self.assertEqual("fixture", marker.read_text(encoding="utf-8"))

    def test_dependency_range_and_plist_template_are_valid(self):
        requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("rumps>=0.4,<0.5", requirements)
        result = subprocess.run(
            ["/usr/bin/plutil", "-lint", str(PROJECT_ROOT / "com.user.codexquota.plist.template")],
            text=True,
            capture_output=True,
            timeout=5,
        )
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
