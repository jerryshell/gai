#!/usr/bin/env python3
"""Tests for native export preflight. These do not run a full export."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def local_engine():
    for name in ("godot", "godot.exe"):
        path = ROOT / ".gai" / "bin" / name
        if path.is_file():
            return str(path)
    macos = ROOT / ".gai" / "bin" / "Godot.app" / "Contents" / "MacOS" / "Godot"
    if macos.is_file():
        return str(macos)
    built = sorted((ROOT / "bin").glob("godot.*.editor.*"))
    for path in built:
        if path.is_file() and ".console." not in path.name:
            return str(path)
    return None


ENGINE = os.environ.get("GAI_GODOT") or local_engine() or shutil.which("godot")


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gai-export-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "project.godot").write_text(
            'config_version=5\n\n[application]\n\nconfig/name="Export Probe"\n'
            'run/main_scene="res://main.tscn"\n',
            encoding="utf-8",
        )
        (self.tmp / "main.tscn").write_text(
            "[gd_scene format=3]\n\n[node name=\"Main\" type=\"Node\"]\n",
            encoding="utf-8",
        )
        self.template = self.tmp / "template.bin"
        self.template.write_text("template\n", encoding="utf-8")
        (self.tmp / "export_presets.cfg").write_text(
            '[preset.0]\n\nname="Linux"\nexport_path="build/linux/game.x86_64"\n\n'
            '[preset.0.options]\n\n'
            f'custom_template/release="{self.template}"\n',
            encoding="utf-8",
        )
        (self.tmp / ".gai").mkdir()
        (self.tmp / ".gai" / "version").write_text("0.0.0-test\n", encoding="utf-8")
        self.env = dict(os.environ)
        self.env["GAI_GAME"] = str(self.tmp)
        self.env["GAI_GODOT"] = ENGINE

    def run_gai(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "bin" / "gai"), *args],
            cwd=str(self.tmp),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
        )

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_dry_run_uses_preset(self):
        output = self.tmp / "out" / "game.x86_64"
        result = self.run_gai("export", "linux", "--dry-run", "--output", str(output))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--export-release Linux", result.stdout)
        self.assertIn(str(output), result.stdout)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_dry_run_uses_export_path(self):
        result = self.run_gai("export", "linux", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("build/linux/game.x86_64", result.stdout)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_missing_preset(self):
        result = self.run_gai("export", "linux", "--preset", "Nope")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("is not in export_presets.cfg", result.stdout)
        self.assertIn("Linux", result.stdout)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_missing_custom_template(self):
        self.template.unlink()
        result = self.run_gai("export", "linux", "--dry-run")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("custom template is missing", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
