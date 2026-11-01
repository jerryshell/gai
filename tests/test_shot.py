#!/usr/bin/env python3
"""End-to-end test for bin/gai shot."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GAI_GODOT") or shutil.which("godot")
HEADLESS = shutil.which("xvfb-run") or os.environ.get("DISPLAY")


def local_engine():
    for pattern in ("bin/godot.linuxbsd.editor.x86_64", "bin/godot.macos.editor.universal", "bin/godot.windows.editor.x86_64.exe"):
        path = ROOT / pattern
        if path.is_file():
            return str(path)
    for name in ("godot", "godot.exe"):
        path = ROOT / ".gai" / "bin" / name
        if path.is_file():
            return str(path)
    macos = ROOT / ".gai" / "bin" / "Godot.app" / "Contents" / "MacOS" / "Godot"
    return str(macos) if macos.is_file() else None


ENGINE = ENGINE or local_engine()


class ShotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gai-shot-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "bin").mkdir()
        shutil.copy2(ROOT / "bin" / "gai", self.tmp / "bin" / "gai")
        shutil.copytree(
            ROOT / "game", self.tmp / "game", ignore=shutil.ignore_patterns(".godot")
        )
        (self.tmp / ".gai").mkdir()
        (self.tmp / ".gai" / "version").write_text("0.0.0-test\n", encoding="utf-8")

    def run_gai(self, *args):
        env = dict(os.environ)
        env["GAI_GODOT"] = ENGINE
        env["GAI_GAME"] = str(self.tmp / "game")
        return subprocess.run(
            [sys.executable, str(self.tmp / "bin" / "gai"), *args],
            cwd=str(self.tmp),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    @unittest.skipUnless(ENGINE, "no engine binary")
    @unittest.skipUnless(HEADLESS, "no display or xvfb-run")
    def test_renders_two_frames(self):
        out = self.tmp / "shots"
        result = self.run_gai(
            "shot", "res://scenes/main.tscn", "--at", "0.2,0.4", "--size", "320x180",
            "--out", str(out), "--name", "frame",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((out / "frame_0.png").is_file())
        self.assertTrue((out / "frame_1.png").is_file())
        self.assertFalse((self.tmp / "game" / ".gai" / "shot").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
