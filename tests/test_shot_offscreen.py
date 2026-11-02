#!/usr/bin/env python3
"""The shot command renders without a display."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def local_engine():
    for pattern in (
        "bin/godot.linuxbsd.editor.x86_64",
        "bin/godot.macos.editor.universal",
        "bin/godot.windows.editor.x86_64.exe",
    ):
        path = ROOT / pattern
        if path.is_file():
            return str(path)
    for name in ("godot", "godot.exe"):
        path = ROOT / ".gai" / "bin" / name
        if path.is_file():
            return str(path)
    macos = ROOT / ".gai" / "bin" / "Godot.app" / "Contents" / "MacOS" / "Godot"
    return str(macos) if macos.is_file() else None


ENGINE = os.environ.get("GAI_GODOT") or local_engine() or shutil.which("godot")


class OffscreenShotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gai-offscreen-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "bin").mkdir()
        shutil.copy2(ROOT / "bin" / "gai", self.tmp / "bin" / "gai")
        shutil.copytree(ROOT / "game", self.tmp / "game", ignore=shutil.ignore_patterns(".godot"))
        (self.tmp / ".gai").mkdir()
        (self.tmp / ".gai" / "version").write_text("0.0.0-test\n", encoding="utf-8")

    def run_gai(self, *args):
        env = dict(os.environ)
        env["GAI_GODOT"] = ENGINE
        env["GAI_GAME"] = str(self.tmp / "game")
        env.pop("DISPLAY", None)
        return subprocess.run(
            [sys.executable, str(self.tmp / "bin" / "gai"), *args],
            cwd=str(self.tmp),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def ensure_import(self) -> None:
        self.run_gai("import")

    def offscreen_supported(self) -> bool:
        """Start the driver directly, so a broken shot is not mistaken for an old engine."""
        assert ENGINE is not None
        result = subprocess.run(
            [
                ENGINE,
                "--path",
                str(self.tmp / "game"),
                "--audio-driver",
                "Dummy",
                "--display-driver",
                "offscreen",
                "--rendering-driver",
                "vulkan",
                "--quit-after",
                "1",
            ],
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
        return result.returncode == 0

    @unittest.skipUnless(ENGINE, "no engine binary")
    def test_renders_without_a_display(self):
        self.ensure_import()
        if not self.offscreen_supported():
            self.skipTest("this engine has no offscreen renderer")
        out = self.tmp / "shots"
        result = self.run_gai(
            "shot",
            "res://scenes/main.tscn",
            "--at",
            "0.2",
            "--size",
            "320x180",
            "--out",
            str(out),
            "--name",
            "frame",
            "--display",
            "offscreen",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        image = out / "frame_0.png"
        self.assertTrue(image.is_file())
        from PIL import Image

        colors = Image.open(image).convert("RGB").getcolors(maxcolors=1 << 20)
        self.assertGreater(len(colors or []), 1, "the frame is a single flat color")


if __name__ == "__main__":
    unittest.main(verbosity=2)
