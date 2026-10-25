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
            "owned_prefixes": [],
            "owned_files": [],
            "edited": [],
        }
        (self.tmp / ".gai" / "upstream.json").write_text(
            json.dumps(state, indent=2) + "\n", encoding="utf-8"
        )

    def run_check(self):
        env = dict(os.environ)
        env["GAI_GODOT"] = ENGINE
        return subprocess.run(
            [sys.executable, str(self.tmp / "bin" / "gai"), "check"],
            cwd=str(self.tmp),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

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
    def test_engine_mismatch_fails(self):
        self.write_state("4.8-stable")
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("does not match upstream 4.8-stable", result.stdout)
        self.assertIn("`version.py` is 4.7.2", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
