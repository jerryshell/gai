#!/usr/bin/env python3
"""Where gai thinks the game is, and what it says about it."""

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


class GameDirTest(unittest.TestCase):
    """The bundled starter game must never win over the project being worked on."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gai-dir-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "bin").mkdir()
        shutil.copy2(ROOT / "bin" / "gai", self.tmp / "bin" / "gai")
        shutil.copytree(
            ROOT / "game", self.tmp / "game", ignore=shutil.ignore_patterns(".godot")
        )
        (self.tmp / ".gai").mkdir()
        (self.tmp / ".gai" / "version").write_text("0.0.0-test\n", encoding="utf-8")
        state = {
            "repo": "https://github.com/godotengine/godot.git",
            "tag": "4.7.2-stable",
            "commit": "0" * 40,
            "merged_at": "2026-10-25",
        }
        (self.tmp / ".gai" / "upstream.json").write_text(
            json.dumps(state, indent=2) + "\n", encoding="utf-8"
        )
        (self.tmp / "version.py").write_text(VERSION_PY, encoding="utf-8")
        self.project = self.tmp / "mygame"
        self.project.mkdir()
        (self.project / "project.godot").write_text(
            'config_version=5\n\n[application]\nconfig/name="test"\n', encoding="utf-8"
        )

    def run_gai(self, *args, cwd=None, game=None):
        env = dict(os.environ)
        env.pop("GAI_GAME", None)
        if game:
            env["GAI_GAME"] = str(game)
        return subprocess.run(
            [sys.executable, str(self.tmp / "bin" / "gai"), *args],
            cwd=str(cwd or self.tmp),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def test_current_directory_wins(self):
        result = self.run_gai("doctor", cwd=self.project)
        self.assertIn(f"game {self.project}", result.stdout, result.stdout + result.stderr)
        self.assertNotIn("bundled starter game", result.stderr)

    def test_env_wins(self):
        result = self.run_gai("doctor", cwd=self.tmp, game=self.project)
        self.assertIn(f"game {self.project}", result.stdout, result.stdout + result.stderr)

    def test_bundled_fallback_is_announced(self):
        result = self.run_gai("doctor", cwd=self.tmp)
        self.assertIn(f"game {self.tmp / 'game'}", result.stdout)
        self.assertIn("bundled starter game", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
