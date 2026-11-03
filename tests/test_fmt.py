#!/usr/bin/env python3
"""End-to-end tests for bin/gai fmt.

The harness copies `bin/gai` and the starter game into a temp root, then runs
the copy as a subprocess. Every formatter here is a shell stand-in: the tests
never need gdformat and never touch the network.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GDFORMAT_SCRIPT = """#!/bin/sh
# A stand-in for gdformat. It records its arguments and exits with a fixed code.
if [ "$1" = "--version" ]; then
    echo "gdformat ${GAI_TEST_VERSION:-4.5.0}"
    exit 0
fi
printf '%s\\n' "$@" > "$GAI_TEST_ARGS"
printf 'formatted %s files\\n' "$#"
if [ -f "$GAI_TEST_MODE" ]; then
    exit "$(cat "$GAI_TEST_MODE")"
fi
exit 0
"""

HOOK_SCRIPT = """#!/bin/sh
# Records one line per argument, so the test can see what gai appended.
{
    printf 'hook=%s\\n' "MARKER"
    for item in "$@"; do
        printf 'arg=%s\\n' "$item"
    done
} > "$GAI_TEST_HOOK"
echo "MARKER ran"
exit 0
"""


class FmtTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gai-fmt-"))
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
        self.args_file = self.tmp / "args.txt"
        self.mode_file = self.tmp / "mode.txt"
        self.hook_file = self.tmp / "hook.txt"
        self.empty_bin = self.tmp / "emptybin"
        self.empty_bin.mkdir()
        self.base_path = f"{self.empty_bin}:/bin:/usr/bin"
        self.extra_env = {}

    # -- helpers ---------------------------------------------------------

    def run_gai(self, *args):
        env = dict(os.environ)
        env["GAI_GAME"] = str(self.game)
        env.pop("GAI_GDFORMAT", None)
        env["PATH"] = self.base_path
        env["GAI_TEST_ARGS"] = str(self.args_file)
        env["GAI_TEST_MODE"] = str(self.mode_file)
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

    def fake_gdformat(self, where="pinned", version="4.5.0"):
        if where == "pinned":
            path = self.game / ".gai" / "tools" / "gdtoolkit-4.5.0" / "bin" / "gdformat"
        else:
            path = self.tmp / "pathbin" / "gdformat"
            self.extra_env["PATH"] = f"{self.tmp / 'pathbin'}:{self.base_path}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(GDFORMAT_SCRIPT, encoding="utf-8")
        path.chmod(0o755)
        self.extra_env["GAI_TEST_VERSION"] = version
        return path

    def write_hook(self, name):
        path = self.game / "tools" / f"{name}.sh"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(HOOK_SCRIPT.replace("MARKER", name), encoding="utf-8")
        return f"sh tools/{name}.sh"

    def add_gai_section(self, **keys):
        text = (self.game / "project.godot").read_text(encoding="utf-8")
        lines = ["", "[gai]", ""]
        for key, value in keys.items():
            lines.append(f'{key}="{value}"')
        (self.game / "project.godot").write_text(text + "\n".join(lines) + "\n", encoding="utf-8")

    def recorded_args(self):
        self.assertTrue(self.args_file.is_file(), "the formatter was never started")
        return self.args_file.read_text(encoding="utf-8").splitlines()

    def recorded_hook(self):
        self.assertTrue(self.hook_file.is_file(), "the project hook was never started")
        return self.hook_file.read_text(encoding="utf-8").splitlines()

    # -- discovery -------------------------------------------------------

    def test_lists_every_script_and_skips_dot_directories(self):
        self.fake_gdformat()
        (self.game / ".hidden").mkdir()
        (self.game / ".hidden" / "skipped.gd").write_text("extends Node\n", encoding="utf-8")
        result = self.run_gai("fmt")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        args = self.recorded_args()
        self.assertIn("scripts/main.gd", args)
        self.assertIn("tests/run_tests.gd", args)
        self.assertFalse([item for item in args if ".hidden" in item or item.startswith(".gai/")])
        self.assertNotIn("--check", args)

    def test_one_path_keeps_only_that_script(self):
        self.fake_gdformat()
        result = self.run_gai("fmt", "scripts/main.gd")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.recorded_args(), ["scripts/main.gd"])

    def test_folder_path_selects_the_scripts_below_it(self):
        self.fake_gdformat()
        result = self.run_gai("fmt", "tests")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        args = self.recorded_args()
        self.assertIn("tests/run_tests.gd", args)
        self.assertNotIn("scripts/main.gd", args)

    def test_unknown_path_is_a_usage_error(self):
        self.fake_gdformat()
        result = self.run_gai("fmt", "scripts/ghost.gd")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("scripts/ghost.gd", result.stderr)
        self.assertFalse(self.args_file.exists())

    # -- the pinned formatter --------------------------------------------

    def test_check_is_clean(self):
        self.fake_gdformat()
        result = self.run_gai("fmt", "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--check", self.recorded_args())

    def test_check_reports_a_dirty_file(self):
        self.fake_gdformat()
        self.mode_file.write_text("1\n", encoding="utf-8")
        result = self.run_gai("fmt", "--check")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("formatted", result.stdout)

    def test_missing_formatter_exits_one(self):
        result = self.run_gai("fmt")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("bin/gai fmt install", result.stderr)

    def test_path_copy_with_the_wrong_version_is_rejected(self):
        self.fake_gdformat(where="path", version="4.4.0")
        result = self.run_gai("fmt", "--check")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("bin/gai fmt install", result.stderr)

    def test_path_copy_with_the_pinned_version_is_accepted(self):
        self.fake_gdformat(where="path", version="4.5.0")
        result = self.run_gai("fmt")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("scripts/main.gd", self.recorded_args())

    def test_gai_gdformat_wins(self):
        elsewhere = self.tmp / "otherbin" / "gdformat"
        elsewhere.parent.mkdir(parents=True, exist_ok=True)
        elsewhere.write_text(GDFORMAT_SCRIPT, encoding="utf-8")
        elsewhere.chmod(0o755)
        self.extra_env["GAI_GDFORMAT"] = str(elsewhere)
        result = self.run_gai("fmt")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("scripts/main.gd", self.recorded_args())

    # -- the project hook ------------------------------------------------

    def test_hook_pair_runs_the_matching_command(self):
        write = self.write_hook("format")
        check = self.write_hook("format_check")
        self.add_gai_section(format_command=write, format_check_command=check)

        result = self.run_gai("fmt")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.recorded_hook()[0], "hook=format")

        self.hook_file.unlink()
        result = self.run_gai("fmt", "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.recorded_hook()[0], "hook=format_check")

    def test_hook_paths_are_appended_and_quoted(self):
        self.add_gai_section(format_check_command=self.write_hook("format_check"))
        (self.game / "scripts" / "two words.gd").write_text("extends Node\n", encoding="utf-8")
        result = self.run_gai("fmt", "--check", "scripts/main.gd", "scripts/two words.gd")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        recorded = self.recorded_hook()
        self.assertEqual(recorded[1], "arg=scripts/main.gd")
        self.assertEqual(recorded[2], "arg=scripts/two words.gd")

    def test_check_without_the_check_key_exits_two(self):
        self.add_gai_section(format_command=self.write_hook("format"))
        result = self.run_gai("fmt", "--check")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("format_check_command", result.stderr)

    def test_hook_runs_with_the_game_as_the_working_directory(self):
        self.add_gai_section(format_command=self.write_hook("format"))
        result = self.run_gai("fmt")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.recorded_hook()[0], "hook=format")

    # -- logs ------------------------------------------------------------

    def test_log_is_written_and_test_xml_is_left_alone(self):
        self.fake_gdformat()
        self.logs.mkdir(parents=True)
        marker = self.logs / "test.xml"
        marker.write_text("<testsuite/>\n", encoding="utf-8")
        result = self.run_gai("fmt", "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        log = (self.logs / "fmt.log").read_text(encoding="utf-8")
        self.assertIn("formatted", log)
        self.assertEqual(marker.read_text(encoding="utf-8"), "<testsuite/>\n")

    def test_hook_output_is_logged(self):
        self.add_gai_section(format_command=self.write_hook("format"))
        result = self.run_gai("fmt")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        log = (self.logs / "fmt.log").read_text(encoding="utf-8")
        self.assertIn("format ran", log)

    # -- install ---------------------------------------------------------

    def test_install_check_accepts_the_pinned_copy(self):
        self.fake_gdformat()
        before = sorted(path.name for path in (self.game / ".gai" / "tools").rglob("*"))
        result = self.run_gai("fmt", "install", "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("4.5.0", result.stdout)
        after = sorted(path.name for path in (self.game / ".gai" / "tools").rglob("*"))
        self.assertEqual(before, after)
        self.assertFalse((self.logs / "fmt-install.log").exists())

    def test_install_check_fails_without_the_pinned_copy(self):
        result = self.run_gai("fmt", "install", "--check")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("not installed", result.stdout)

    def test_install_check_rejects_the_wrong_version(self):
        self.fake_gdformat(version="4.4.0")
        result = self.run_gai("fmt", "install", "--check")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("4.4.0", result.stdout)

    def test_install_rejects_unknown_arguments(self):
        result = self.run_gai("fmt", "install", "--force")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
