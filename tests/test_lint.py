#!/usr/bin/env python3
"""End-to-end tests for bin/gai lint.

The harness copies `bin/gai` and the starter game into a temp root, then runs
the copy as a subprocess. The engine groups need a Godot binary: set
`GAI_GODOT`, or install one into `.gai/bin`. Without one they skip.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BROKEN_SCRIPT = "extends Node\n\nfunc _ready( -> void:\n\tpass\n"


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
NO_ENGINE = "no engine binary: set GAI_GODOT to run the engine lint groups"

HOOK_SCRIPT = """#!/bin/sh
# Records one line per argument, so the test can see what gai appended.
{
    printf 'hook=lint\\n'
    for item in "$@"; do
        printf 'arg=%s\\n' "$item"
    done
} > "$GAI_TEST_HOOK"
echo "lint_command ran"
exit 0
"""

MEASURED = """gai v4.7.2.stable.custom_build

SCRIPT ERROR: Parse Error: Cannot assign a value of type "String" as "int".
          at: GDScript::reload (res://scripts/broken.gd:4)
          GDScript backtrace (most recent call first):
              [0] _ready (res://.gai/check/gai_check.gd:18)
ERROR: Failed to load script "res://scripts/broken.gd" with error "Parse error".
   at: load (modules/gdscript/gdscript_resource_format.cpp:46)
SCRIPT ERROR: Parse Error: "for" iterator variable "key" has no static type. (Warning treated as error.)
          at: GDScript::reload (res://tests/loop.gd:12)
ERROR: 2 RID allocations of type 'N10Particles' were leaked at exit.
          at: GDScript::reload (res://tests/leaked.gd:1)
gai-check: 9 scripts
"""


def gai_module():
    loader = SourceFileLoader("gai_cli", str(ROOT / "bin" / "gai"))
    spec = spec_from_loader("gai_cli", loader)
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


class LintProblemsTest(unittest.TestCase):
    """The parser, without an engine."""

    def setUp(self):
        self.gai = gai_module()

    def test_attribution(self):
        problems = self.gai.lint_problems(MEASURED)
        self.assertEqual(
            problems,
            [
                ("scripts/broken.gd", 4, 'Parse Error: Cannot assign a value of type "String" as "int".'),
                (
                    "tests/loop.gd",
                    12,
                    'Parse Error: "for" iterator variable "key" has no static type. (Warning treated as error.)',
                ),
            ],
        )

    def test_shutdown_noise_is_dropped(self):
        problems = self.gai.lint_problems(MEASURED)
        self.assertFalse([item for item in problems if item[0] == "tests/leaked.gd"])

    def test_clean_output_has_no_problems(self):
        self.assertEqual(self.gai.lint_problems("gai-check: 9 scripts\n"), [])


class LintTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gai-lint-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "bin").mkdir()
        shutil.copy2(ROOT / "bin" / "gai", self.tmp / "bin" / "gai")
        shutil.copytree(ROOT / "game", self.tmp / "game", ignore=shutil.ignore_patterns(".godot"))
        (self.tmp / ".gai").mkdir()
        (self.tmp / ".gai" / "version").write_text("0.0.0-test\n", encoding="utf-8")
        (self.tmp / ".gai" / "upstream.json").write_text(
            json.dumps(
                {
                    "repo": "https://github.com/godotengine/godot.git",
                    "tag": "4.7.2-stable",
                    "commit": "0" * 40,
                    "merged_at": "2026-10-25",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.game = self.tmp / "game"
        self.logs = self.game / ".gai" / "logs"
        self.hook_file = self.tmp / "hook.txt"
        self.empty_bin = self.tmp / "emptybin"
        self.empty_bin.mkdir()
        self.extra_env = {
            "PATH": f"{self.empty_bin}:/bin:/usr/bin",
        }

    # -- helpers ---------------------------------------------------------

    def run_gai(self, *args):
        env = dict(os.environ)
        env["GAI_GAME"] = str(self.game)
        env.pop("GAI_GODOT", None)
        env["GAI_TEST_HOOK"] = str(self.hook_file)
        env.update(self.extra_env)
        return subprocess.run(
            [sys.executable, str(self.tmp / "bin" / "gai"), *args],
            cwd=str(self.tmp),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def run_lint(self, *args):
        self.extra_env["GAI_GODOT"] = ENGINE
        return self.run_gai("lint", *args)

    def write_hook(self):
        path = self.game / "tools" / "lint.sh"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(HOOK_SCRIPT, encoding="utf-8")
        text = (self.game / "project.godot").read_text(encoding="utf-8")
        text += '\n[gai]\n\nlint_command="sh tools/lint.sh"\n'
        (self.game / "project.godot").write_text(text, encoding="utf-8")

    def break_script(self, name="scripts/broken.gd"):
        path = self.game / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(BROKEN_SCRIPT, encoding="utf-8")
        return name

    # -- the engine backend ----------------------------------------------

    @unittest.skipUnless(ENGINE, NO_ENGINE)
    def test_clean_project_exits_zero(self):
        result = self.run_lint()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 problems", result.stdout)
        # The count follows the fixture, so assert the shape and not a number.
        self.assertRegex(result.stdout, r"lint: \d+ scripts, 0 problems")

    @unittest.skipUnless(ENGINE, NO_ENGINE)
    def test_broken_script_is_attributed(self):
        self.break_script()
        result = self.run_lint()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("scripts/broken.gd:3: Parse Error:", result.stdout)
        self.assertIn("1 problems", result.stdout)

    @unittest.skipUnless(ENGINE, NO_ENGINE)
    def test_paths_filter(self):
        self.break_script("scripts/broken.gd")
        result = self.run_lint("scripts/main.gd")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("lint: 1 scripts", result.stdout)
        self.assertNotIn("broken", result.stdout)

        result = self.run_lint("scripts/broken.gd")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("scripts/broken.gd:3:", result.stdout)

    @unittest.skipUnless(ENGINE, NO_ENGINE)
    def test_log_is_written_and_test_xml_is_left_alone(self):
        self.logs.mkdir(parents=True, exist_ok=True)
        marker = self.logs / "test.xml"
        marker.write_text("<testsuite/>\n", encoding="utf-8")
        self.break_script()
        result = self.run_lint()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        log = (self.logs / "lint.log").read_text(encoding="utf-8")
        self.assertIn("GDScript::reload", log)
        self.assertEqual(marker.read_text(encoding="utf-8"), "<testsuite/>\n")

    # -- the project hook ------------------------------------------------

    def test_override_runs_without_an_engine(self):
        self.write_hook()
        self.extra_env["GAI_GODOT"] = str(self.tmp / "no-engine-here")
        result = self.run_gai("lint")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("no engine", result.stderr)
        self.assertIn("lint_command ran", result.stdout)

    def test_override_paths_are_appended_and_quoted(self):
        self.write_hook()
        (self.game / "scripts" / "two words.gd").write_text("extends Node\n", encoding="utf-8")
        self.extra_env["GAI_GODOT"] = str(self.tmp / "no-engine-here")
        result = self.run_gai("lint", "scripts/main.gd", "scripts/two words.gd")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        recorded = self.hook_file.read_text(encoding="utf-8").splitlines()
        self.assertEqual(recorded, ["hook=lint", "arg=scripts/main.gd", "arg=scripts/two words.gd"])

    def test_override_log_is_written(self):
        self.write_hook()
        self.extra_env["GAI_GODOT"] = str(self.tmp / "no-engine-here")
        result = self.run_gai("lint")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        log = (self.logs / "lint.log").read_text(encoding="utf-8")
        self.assertIn("lint_command ran", log)

    # -- usage -----------------------------------------------------------

    def test_unknown_path_exits_two(self):
        result = self.run_gai("lint", "scripts/ghost.gd")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("scripts/ghost.gd", result.stderr)
        self.assertFalse(self.hook_file.exists())


if __name__ == "__main__":
    unittest.main(verbosity=1)
