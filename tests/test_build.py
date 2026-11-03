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

    def run_gai(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(self.tmp / "bin" / "gai"), *args],
            cwd=str(self.tmp),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def cache_env(self, *names):
        """A PATH that holds only these fake cache launchers, with private cache folders."""
        bindir = self.tmp / "fakebin"
        bindir.mkdir(exist_ok=True)
        for name in names:
            launcher = bindir / name
            launcher.write_text(
                '#!/bin/sh\necho "$*" >> "$CACHE_LOG"\nexit 0\n',
                encoding="utf-8",
            )
            launcher.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = str(bindir)
        env["CCACHE_DIR"] = str(self.tmp / "cache" / "ccache")
        env["SCCACHE_DIR"] = str(self.tmp / "cache" / "sccache")
        env["CACHE_LOG"] = str(self.cache_log())
        for variable in ("CC", "CXX"):
            env.pop(variable, None)
        return env

    def engine(self):
        return self.tmp / "bin" / "godot.linuxbsd.editor.x86_64"

    def cache_log(self):
        (self.tmp / "cache").mkdir(parents=True, exist_ok=True)
        return self.tmp / "cache" / "launcher.log"

    def wrapper(self, name, language):
        return self.tmp / ".gai" / "tools" / "cache" / f"{name}-{language}"

    def test_dry_run_prints_command(self):
        result = self.run_gai("build", "--dry-run", "--jobs", "2")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("scons", result.stdout)
        self.assertIn("-j2", result.stdout)

    def test_no_engine(self):
        result = self.run_gai("build", "--check")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("no editor binary", result.stdout)

    def test_template_dry_run(self):
        result = self.run_gai(
            "build",
            "--dry-run",
            "--jobs",
            "2",
            "--target",
            "template_release",
            "--platform",
            "windows",
            "--mingw",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("target=template_release", result.stdout)
        self.assertIn("platform=windows", result.stdout)
        self.assertIn("use_mingw=yes", result.stdout)

    def test_template_check(self):
        result = self.run_gai("build", "--check", "--target", "template_release")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("no template_release binary", result.stdout)

        template = self.tmp / "bin" / "godot.linuxbsd.template_release.x86_64"
        template.write_text("", encoding="utf-8")
        now = time.time()
        os.utime(template, (now, now))
        result = self.run_gai("build", "--check", "--target", "template_release")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("up to date", result.stdout)

    def test_cache_prefix_in_dry_run(self):
        env = self.cache_env("ccache")
        result = self.run_gai("build", "--dry-run", "--jobs", "2", env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"build: cache ccache ({self.tmp / 'cache' / 'ccache'})", result.stdout)
        self.assertIn(f'CC="{self.wrapper("ccache", "cc")}"', result.stdout)
        self.assertIn(f'CXX="{self.wrapper("ccache", "cxx")}"', result.stdout)
        lines = result.stdout.splitlines()
        self.assertTrue(lines[0].startswith("build: cache ccache"), lines[0])
        self.assertIn("scons", lines[1])

    def test_cache_keeps_the_chosen_compiler(self):
        env = self.cache_env("ccache")
        env["CC"] = "gcc-13"
        env["CXX"] = "g++-13"
        result = self.run_gai("build", "--dry-run", env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("gcc-13", self.wrapper("ccache", "cc").read_text(encoding="utf-8"))
        self.assertIn("g++-13", self.wrapper("ccache", "cxx").read_text(encoding="utf-8"))

    def test_wrapper_runs_the_cache_and_the_compiler(self):
        """The wrapper is the whole mechanism: run it and read what the cache saw."""
        env = self.cache_env("ccache")
        result = self.run_gai("build", "--dry-run", env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        wrapper = self.wrapper("ccache", "cc")
        self.assertTrue(os.access(wrapper, os.X_OK), wrapper)
        done = subprocess.run([str(wrapper), "-c", "unit.c"], env=env, text=True, capture_output=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("cc -c unit.c", self.cache_log().read_text(encoding="utf-8"))

    def test_a_compiler_that_already_has_a_launcher_is_not_wrapped_again(self):
        env = self.cache_env("ccache")
        env["CC"] = "ccache gcc"
        result = self.run_gai("build", "--dry-run", env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('CC="', result.stdout)
        self.assertIn('CXX="', result.stdout)

    def test_sccache_wins_and_uses_its_directory(self):
        env = self.cache_env("sccache", "ccache")
        result = self.run_gai("build", "--dry-run", env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"build: cache sccache ({self.tmp / 'cache' / 'sccache'})", result.stdout)
        self.assertIn(f'CC="{self.wrapper("sccache", "cc")}"', result.stdout)

    def test_no_cache_option_removes_the_prefix_and_the_line(self):
        env = self.cache_env("ccache")
        result = self.run_gai("build", "--dry-run", "--jobs", "2", "--no-cache", env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("cache", result.stdout)
        self.assertNotIn("ccache", result.stdout)
        self.assertIn("-j2", result.stdout)

    def test_no_cache_on_path(self):
        env = self.cache_env()
        result = self.run_gai("build", "--dry-run", env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "build: cache none (install ccache or sccache for faster rebuilds)",
            result.stdout,
        )
        self.assertNotIn("CC=", result.stdout)

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
