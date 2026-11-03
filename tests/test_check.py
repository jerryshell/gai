#!/usr/bin/env python3
"""End-to-end tests for bin/gai check."""

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


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gai-check-"))
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
        self.write_state("4.7.2-stable")
        (self.tmp / "version.py").write_text(VERSION_PY, encoding="utf-8")

    def write_state(self, tag: str) -> None:
        state = {
            "repo": "https://github.com/godotengine/godot.git",
            "tag": tag,
            "commit": "0" * 40,
            "merged_at": "2026-10-25",
        }
        (self.tmp / ".gai" / "upstream.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

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

    def run_check(self):
        return self.run_gai("check")

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_clean_game_passes(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("check: ok", result.stdout)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_parse_error_fails(self):
        (self.tmp / "game" / "scripts" / "main.gd").write_text(
            "extends Node2D\n\nfunc _ready( -> void:\n\tpass\n", encoding="utf-8"
        )
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Parse Error", result.stdout)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_single_script_check(self):
        (self.tmp / "game" / "scripts" / "main.gd").write_text(
            "extends Node2D\n\nfunc _ready( -> void:\n\tpass\n", encoding="utf-8"
        )
        result = self.run_gai("check", "--no-tests", "--no-run", "--script", "res://scripts/main.gd")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Parse Error", result.stdout)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_orphaned_sidecar_fails(self):
        (self.tmp / "game" / "ghost.gd.uid").write_text("uid://abc\n", encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("ghost.gd.uid has no target left", result.stderr)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_bootstrap_with_engine(self):
        result = self.run_gai("bootstrap")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("check: ok", result.stdout)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_engine_mismatch_fails(self):
        self.write_state("4.8-stable")
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("does not match upstream 4.8-stable", result.stdout)
        self.assertIn("`version.py` is 4.7.2", result.stdout)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_clean_check_writes_an_ok_record(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = json.loads((self.tmp / ".gai" / "logs" / "diagnostics.json").read_text(encoding="utf-8"))
        self.assertEqual(record["schema"], 1)
        self.assertEqual(record["source"], "check")
        self.assertTrue(record["ok"])
        self.assertEqual(record["count"], 0)
        self.assertIsNone(record["first"])

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_error_record_names_path_and_line(self):
        (self.tmp / "game" / "scripts" / "main.gd").write_text(
            "extends Node2D\n\nfunc _ready( -> void:\n\tpass\n", encoding="utf-8"
        )
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        record = json.loads((self.tmp / ".gai" / "logs" / "diagnostics.json").read_text(encoding="utf-8"))
        self.assertFalse(record["ok"])
        first = record["first"]
        self.assertEqual(first["path"], "res://scripts/main.gd")
        self.assertEqual(first["line"], 3)
        self.assertIn("Parse Error", first["message"])
        self.assertEqual(first["severity"], "error")
        self.assertEqual(record["errors"][0], first)

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_json_flag_prints_the_record(self):
        (self.tmp / "game" / "scripts" / "main.gd").write_text(
            "extends Node2D\n\nfunc _ready( -> void:\n\tpass\n", encoding="utf-8"
        )
        result = self.run_gai("check", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        record = json.loads(result.stdout)
        self.assertFalse(record["ok"])
        self.assertEqual(record["first"]["path"], "res://scripts/main.gd")


class DiagnosticsParseTest(unittest.TestCase):
    """The parser, without an engine."""

    MEASURED = """gai-check: loading 3 scripts
SCRIPT ERROR: Parse Error: Cannot find member \"hp\" in base \"Node2D\".
          at: GDScript::reload (res://scripts/player.gd:7)
ERROR: Cannot open file 'res://missing.tres'.
          at: load (res://scripts/player.gd:12)
ERROR: 2 RID allocations of type 'N10Particles' were leaked at exit.
          at: GDScript::reload (res://tests/leaked.gd:1)
SCRIPT ERROR: Parse Error: Expected parameter name.
          at: GDScript::reload (res://scripts/player.gd:7)
"""

    def setUp(self):
        self.gai = gai_module()

    def test_records_carry_path_and_line(self):
        records = self.gai.parse_diagnostics(self.MEASURED, "check")
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["path"], "res://scripts/player.gd")
        self.assertEqual(records[0]["line"], 7)
        self.assertEqual(records[0]["kind"], "script")
        self.assertIn("Cannot find member", records[0]["message"])
        self.assertEqual(records[1]["path"], "res://scripts/player.gd")
        self.assertEqual(records[1]["line"], 12)

    def test_repeats_collapse(self):
        records = self.gai.parse_diagnostics("\n".join([self.MEASURED, self.MEASURED]), "check")
        self.assertEqual(len(records), 3)

    def test_shutdown_noise_is_not_a_record(self):
        records = self.gai.parse_diagnostics(self.MEASURED, "check")
        self.assertFalse([record for record in records if "leaked" in record["message"]])

    def test_clean_output_is_an_ok_record(self):
        record = self.gai.diagnostics_record("check", self.gai.parse_diagnostics("all good\n", "check"))
        self.assertTrue(record["ok"])
        self.assertEqual(record["count"], 0)
        self.assertIsNone(record["first"])

    def test_unplaced_error_is_kept(self):
        records = self.gai.parse_diagnostics("ERROR: something went wrong outside a script\n", "check")
        self.assertEqual(len(records), 1)
        self.assertIsNone(records[0]["path"])
        self.assertEqual(records[0]["kind"], "engine")


def gai_module():
    from importlib.machinery import SourceFileLoader
    from importlib.util import module_from_spec, spec_from_loader

    loader = SourceFileLoader("gai_cli", str(ROOT / "bin" / "gai"))
    spec = spec_from_loader("gai_cli", loader)
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main(verbosity=1)
