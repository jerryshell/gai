#!/usr/bin/env python3
"""Tests for bin/gai init. These do not need an engine."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class InitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gai-init-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "project.godot").write_text(
            'config_version=5\n\n[application]\n\nconfig/name="Init Probe"\nrun/main_scene="res://main.tscn"\n',
            encoding="utf-8",
        )
        (self.tmp / "main.tscn").write_text(
            '[gd_scene format=3]\n\n[node name="Main" type="Node"]\n',
            encoding="utf-8",
        )

    def run_gai(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "bin" / "gai"), *args],
            cwd=str(self.tmp),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_harness_project(self):
        result = self.run_gai("init", str(self.tmp))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for path in (
            "AGENTS.md",
            "docs/gai.md",
            "tests/gai_test_case.gd",
            "tests/run_tests.gd",
            "tests/test_project.gd",
            ".gai/mcp.json",
        ):
            self.assertTrue((self.tmp / path).is_file(), path)
        agents = (self.tmp / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(f"GAI_GAME={self.tmp}", agents)
        self.assertIn("tests/run_tests.gd", agents)
        mcp = json.loads((self.tmp / ".gai" / "mcp.json").read_text(encoding="utf-8"))
        self.assertIn("gai", mcp["mcpServers"])
        self.assertEqual(mcp["mcpServers"]["gai"]["env"]["GAI_GAME"], str(self.tmp))

    def test_scene_project_keeps_harness_out(self):
        (self.tmp / "tests").mkdir()
        (self.tmp / "tests" / "scene_test.gd").write_text(
            "extends Node\n\nfunc _ready() -> void:\n\tget_tree().quit(0)\n",
            encoding="utf-8",
        )
        (self.tmp / "tests" / "scene_test.tscn").write_text(
            "[gd_scene load_steps=2 format=3]\n\n"
            '[ext_resource type="Script" path="res://tests/scene_test.gd" id="1"]\n\n'
            '[node name="SceneTest" type="Node"]\nscript = ExtResource("1")\n',
            encoding="utf-8",
        )
        result = self.run_gai("init", str(self.tmp))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.tmp / "tests" / "run_tests.gd").exists())
        agents = (self.tmp / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("--scene-dir res://tests", agents)
        self.assertIn("scene tests", agents)

    def test_keeps_existing_files_without_force(self):
        (self.tmp / "AGENTS.md").write_text("custom\n", encoding="utf-8")
        result = self.run_gai("init", str(self.tmp))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.tmp / "AGENTS.md").read_text(encoding="utf-8"), "custom\n")

        forced = self.run_gai("init", str(self.tmp), "--force")
        self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
        self.assertIn("agent guide", (self.tmp / "AGENTS.md").read_text(encoding="utf-8"))

    def test_no_mcp(self):
        result = self.run_gai("init", str(self.tmp), "--no-mcp")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.tmp / ".gai" / "mcp.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=1)
