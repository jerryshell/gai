#!/usr/bin/env python3
"""Tests for bin/gai build. These do not need SCons or an engine."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gai-build-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "bin").mkdir()
        shutil.copy2(ROOT / "bin" / "gai", self.tmp / "bin" / "gai")
        (self.tmp / ".gai").mkdir()
        (self.tmp / ".gai" / "version").write_text("0.0.0-test\n", encoding="utf-8")

    def run_gai(self, *args):
        return subprocess.run(
            [sys.executable, str(self.tmp / "bin" / "gai"), *args],
            cwd=str(self.tmp),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def engine(self):
        return self.tmp / "bin" / "godot.linuxbsd.editor.x86_64"

    def test_dry_run_prints_command(self):
        result = self.run_gai("build", "--dry-run", "--jobs", "2")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("scons", result.stdout)
        self.assertIn("-j2", result.stdout)

    def test_no_engine(self):
        result = self.run_gai("build", "--check")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("no engine", result.stdout)

    def test_detects_newer_source_and_current_binary(self):
        now = time.time()
        self.engine().write_text("", encoding="utf-8")
        os.utime(self.engine(), (now, now))
        source = self.tmp / "core" / "fake.cpp"
        source.parent.mkdir(parents=True)
        source.write_text("// probe\n", encoding="utf-8")
        os.utime(source, (now + 10, now + 10))

        stale = self.run_gai("build", "--check")
        self.assertEqual(stale.returncode, 1, stale.stdout + stale.stderr)
        self.assertIn("stale", stale.stdout)
        self.assertIn("core/fake.cpp", stale.stdout)

        os.utime(source, (now - 10, now - 10))
        current = self.run_gai("build", "--check")
        self.assertEqual(current.returncode, 0, current.stdout + current.stderr)
        self.assertIn("up to date", current.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
