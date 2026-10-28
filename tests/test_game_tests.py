#!/usr/bin/env python3
"""End-to-end tests for bin/gai test and the check integration."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_PY = (
    'short_name = "godot"\nname = "gai"\nmajor = 4\nminor = 7\npatch = 2\n'
    'status = "stable"\nmodule_config = ""\n'
    'website = "https://github.com/jerryshell/gai"\ndocs = "4.7"\n'
)


def local_engine():
    for name in ("godot", "godot.exe"):
        path = ROOT / ".gai" / "bin" / name
        if path.is_file():
            return str(path)
    macos = ROOT / ".gai" / "bin" / "Godot.app" / "Contents" / "MacOS" / "Godot"
    if macos.is_file():
        return str(macos)
    return None


ENGINE = os.environ.get("GAI_GODOT") or local_engine() or shutil.which("godot")


class GameTestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gai-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "bin").mkdir()
        shutil.copy2(ROOT / "bin" / "gai", self.tmp / "bin" / "gai")
        shutil.copytree(
            ROOT / "game",
            self.tmp / "game",
            ignore=shutil.ignore_patterns(".godot"),
        )
        (self.tmp / ".gai").mkdir()
        (self.tmp / ".gai" / "version").write_text("0.0.0-test\n", encoding="utf-8")
        (self.tmp / "version.py").write_text(VERSION_PY, encoding="utf-8")
        state = {
            "repo": "https://github.com/godotengine/godot.git",
            "tag": "4.7.2-stable",
            "commit": "0" * 40,
            "merged_at": "2026-10-25",
        }
        (self.tmp / ".gai" / "upstream.json").write_text(
            json.dumps(state, indent=2) + "\n", encoding="utf-8"
        )

    def run_gai(self, *args):
        env = dict(os.environ)
        env["GAI_GODOT"] = ENGINE
        return subprocess.run(
            [sys.executable, str(self.tmp / "bin" / "gai"), *args],
            cwd=str(self.tmp),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def write_failing_test(self):
        (self.tmp / "game" / "tests" / "test_zz_fail.gd").write_text(
            "extends \"res://tests/gai_test_case.gd\"\n\n"
            "func test_math() -> void:\n"
            "\tassert_eq(2 + 2, 5, \"math is broken\")\n",
            encoding="utf-8",
        )

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_sample_tests_pass(self):
        result = self.run_gai("test")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 failed", result.stdout)
        self.assertIn("tests:", result.stdout)
        junit = (self.tmp / ".gai" / "logs" / "test.xml").read_text(encoding="utf-8")
        self.assertIn("<testsuite", junit)
        self.assertIn('failures="0"', junit)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_json_output(self):
        result = self.run_gai("test", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertGreaterEqual(payload["passed"], 2)
        self.assertEqual(payload["failed"], 0)
        self.assertGreaterEqual(payload["tests"], payload["passed"])

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_failing_test_fails(self):
        self.write_failing_test()
        result = self.run_gai("test", "--filter", "zz_fail")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("expected 5, got 4", result.stdout)
        self.assertIn("1 failed", result.stdout)
        junit = (self.tmp / ".gai" / "logs" / "test.xml").read_text(encoding="utf-8")
        self.assertIn("<failure", junit)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_filter_without_match_fails(self):
        result = self.run_gai("test", "--filter", "no_such_test")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("no tests matched", result.stdout)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_parse_error_fails(self):
        (self.tmp / "game" / "tests" / "test_broken.gd").write_text(
            "extends \"res://tests/gai_test_case.gd\"\n\n"
            "func test_broken( -> void:\n"
            "\tpass\n",
            encoding="utf-8",
        )
        result = self.run_gai("test", "--filter", "broken")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("cannot load or instantiate", result.stdout)
        self.assertIn("Parse Error", result.stdout)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_scene_tests(self):
        tests = self.tmp / "game" / "tests"
        (tests / "scene_probe_pass.gd").write_text(
            "extends Node\n\nfunc _ready() -> void:\n"
            "\tprint(\"scene probe pass\")\n\tget_tree().quit(0)\n",
            encoding="utf-8",
        )
        (tests / "scene_probe_fail.gd").write_text(
            "extends Node\n\nfunc _ready() -> void:\n"
            "\tpush_error(\"scene probe failure\")\n\tget_tree().quit(1)\n",
            encoding="utf-8",
        )
        (tests / "scene_probe_pass.tscn").write_text(
            '[gd_scene load_steps=2 format=3]\n\n'
            '[ext_resource type="Script" path="res://tests/scene_probe_pass.gd" id="1"]\n\n'
            '[node name="SceneProbePass" type="Node"]\nscript = ExtResource("1")\n',
            encoding="utf-8",
        )
        (tests / "scene_probe_fail.tscn").write_text(
            '[gd_scene load_steps=2 format=3]\n\n'
            '[ext_resource type="Script" path="res://tests/scene_probe_fail.gd" id="1"]\n\n'
            '[node name="SceneProbeFail" type="Node"]\nscript = ExtResource("1")\n',
            encoding="utf-8",
        )
        result = self.run_gai("test", "--scene-dir", "res://tests", "--filter", "scene_probe")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("1 passed, 1 failed", result.stdout)
        self.assertIn("scene probe failure", result.stdout)
        junit = (self.tmp / ".gai" / "logs" / "scene-test.xml").read_text(encoding="utf-8")
        self.assertIn("<failure", junit)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_isolate_passes(self):
        result = self.run_gai("test", "--isolate")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 failed", result.stdout)
        self.assertIn("junit:", result.stdout)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_isolate_timeout(self):
        (self.tmp / "game" / "tests" / "test_zz_hang.gd").write_text(
            "extends \"res://tests/gai_test_case.gd\"\n\n"
            "func test_hang() -> void:\n"
            "\twhile true:\n"
            "\t\tpass\n",
            encoding="utf-8",
        )
        result = self.run_gai("test", "--isolate-tests", "--file-timeout", "2")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("test_zz_hang.gd::test_hang", result.stdout)
        self.assertIn("timed out after 2.0s", result.stdout)
        self.assertIn("1 failed", result.stdout)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_check_runs_tests(self):
        self.write_failing_test()
        result = self.run_gai("check")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("test_zz_fail.gd::test_math", result.stdout)
        self.assertIn("expected 5, got 4", result.stdout)

        skipped = self.run_gai("check", "--no-tests")
        self.assertEqual(skipped.returncode, 0, skipped.stdout + skipped.stderr)
        self.assertIn("check: ok", skipped.stdout)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_no_tests_passes(self):
        (self.tmp / "game" / "tests" / "run_tests.gd").unlink()
        result = self.run_gai("test")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("no tests", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
