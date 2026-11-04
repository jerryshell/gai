#!/usr/bin/env python3
"""Tests for bin/gai next. These do not need SCons or an engine."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class NextTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gai-next-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "bin").mkdir()
        shutil.copy2(ROOT / "bin" / "gai", self.tmp / "bin" / "gai")
        (self.tmp / ".gai").mkdir()
        (self.tmp / ".gai" / "version").write_text("0.0.0-test\n", encoding="utf-8")
        (self.tmp / "game").mkdir()
        (self.tmp / "game" / "project.godot").write_text(
            'config_version=5\n\n[application]\n\nrun/main_scene="res://scenes/main.tscn"\n',
            encoding="utf-8",
        )

    def run_gai(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(self.tmp / "bin" / "gai"), *args],
            cwd=str(self.tmp),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def external_game(self):
        """A project outside the repository, the way GAI_GAME points at one."""
        project = self.tmp / "external"
        (project / "components").mkdir(parents=True)
        (project / "tests").mkdir()
        (project / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        for path in ("components/ability.gd", "components/scene.tscn", "tests/p0_test.gd"):
            (project / path).write_text("extends Node\n", encoding="utf-8")
        env = dict(os.environ)
        env["GAI_GAME"] = str(project)
        return project, env

    def test_external_project_scripts_use_the_script_gate(self):
        project, env = self.external_game()
        result = self.run_gai("next", "--json", str(project / "components" / "ability.gd"), env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["gate"], "script")
        self.assertEqual(payload["reasons"][0]["rule"], "<game>/**/*.gd")
        self.assertEqual(
            payload["command"],
            "bin/gai check --script res://components/ability.gd --no-run",
        )

        relative = self.run_gai("next", "--json", "components/scene.tscn", env=env)
        self.assertEqual(json.loads(relative.stdout)["gate"], "check")

        tests = self.run_gai("next", "--json", "tests/p0_test.gd", env=env)
        self.assertEqual(json.loads(tests.stdout)["reasons"][0]["rule"], "<game>/tests/**")

    def gate(self, *paths):
        result = self.run_gai("next", *paths)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_game_script_gate(self):
        stdout = self.gate("game/scripts/player.gd")
        self.assertIn("next: gate script", stdout)
        self.assertIn("next: bin/gai check --script res://scripts/player.gd --no-run", stdout)
        self.assertNotIn("next: bin/gai check\n", stdout)

    def test_each_script_gets_its_own_command(self):
        stdout = self.gate("game/scripts/player.gd", "game/scripts/enemy.gd")
        self.assertIn("--script res://scripts/player.gd --no-run", stdout)
        self.assertIn("--script res://scripts/enemy.gd --no-run", stdout)
        self.assertEqual(stdout.count("next: bin/gai check --script"), 2)

    def test_game_scene_gate(self):
        stdout = self.gate("game/scenes/main.tscn")
        self.assertIn("next: gate check", stdout)
        self.assertIn("next: bin/gai check\n", stdout)

    def test_game_asset_and_autoload_gate(self):
        for path in ("game/assets/icon.png", "game/project.godot", "game/scripts/game.gd.bak"):
            with self.subTest(path=path):
                stdout = self.gate(path)
                self.assertIn("next: gate check", stdout)

    def test_project_file_outside_the_starter_game(self):
        stdout = self.gate("somewhere/project.godot")
        self.assertIn("next: gate check", stdout)

    def test_game_test_gate(self):
        stdout = self.gate("game/tests/test_player.gd")
        self.assertIn("next: gate check", stdout)
        self.assertNotIn("--script", stdout)

    def test_engine_source_dirs(self):
        paths = (
            "core/object/object.cpp",
            "scene/main/node.cpp",
            "servers/rendering/renderer.cpp",
            "modules/gai_agent/gai_agent_server.cpp",
            "platform/linuxbsd/detect.py",
            "editor/editor_node.cpp",
            "main/main.cpp",
            "drivers/unix/file_access.cpp",
        )
        for path in paths:
            with self.subTest(path=path):
                stdout = self.gate(path)
                self.assertIn("next: gate rebuild-check", stdout)
                self.assertIn("next: bin/gai build\n", stdout)
                self.assertIn("next: bin/gai check\n", stdout)

    def test_engine_build_files(self):
        for path in ("SConstruct", "methods.py", "version.py", ".gai/features/agent.json"):
            with self.subTest(path=path):
                self.assertIn("next: gate rebuild-check", self.gate(path))

    def test_docs_and_ci_need_no_gate(self):
        paths = (
            "docs/gai/build.md",
            "docs/gai/architecture.md",
            "AGENTS.md",
            "README.md",
            "modules/gai_agent/README.md",
            "tests/test_build.py",
            ".github/workflows/gai.yml",
        )
        for path in paths:
            with self.subTest(path=path):
                stdout = self.gate(path)
                self.assertIn("next: gate none", stdout)
                self.assertIn("next: nothing to run", stdout)

    def test_unknown_path_needs_a_check(self):
        stdout = self.gate("mystery/data.bin")
        self.assertIn("next: gate check", stdout)

    def test_mixed_change_picks_the_highest_gate(self):
        stdout = self.gate("docs/gai/build.md", "game/scripts/player.gd", "game/main.tscn")
        self.assertIn("next: gate check", stdout)

        stdout = self.gate("game/scripts/player.gd", "core/object/object.cpp")
        self.assertIn("next: gate rebuild-check", stdout)

        stdout = self.gate("docs/gai/build.md", "game/scripts/player.gd")
        self.assertIn("next: gate script", stdout)

    def test_json_shape(self):
        result = self.run_gai("next", "--json", "game/scripts/player.gd", "docs/gai/build.md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(sorted(payload), ["command", "gate", "paths", "reasons"])
        self.assertEqual(payload["gate"], "script")
        self.assertEqual(payload["command"], "bin/gai check --script res://scripts/player.gd --no-run")
        self.assertEqual(payload["paths"], ["game/scripts/player.gd", "docs/gai/build.md"])
        self.assertEqual(
            payload["reasons"],
            [
                {"path": "game/scripts/player.gd", "gate": "script", "rule": "game/**/*.gd"},
                {"path": "docs/gai/build.md", "gate": "none", "rule": "docs/**"},
            ],
        )

    def test_an_engine_source_adds_a_template_object_step(self):
        stdout = self.gate("modules/gai_agent/gai_agent_server.cpp")
        self.assertIn("next: gate rebuild-check", stdout)
        self.assertIn(
            "next: bin/gai build --target template_release --objects modules/gai_agent/gai_agent_server.cpp",
            stdout,
        )
        header = self.gate("modules/gai_agent/gai_agent_server.h")
        self.assertNotIn("--objects", header)

    def test_json_for_engine_change(self):
        result = self.run_gai("next", "--json", "core/object/object.cpp")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["gate"], "rebuild-check")
        self.assertEqual(
            payload["command"],
            "bin/gai build && bin/gai build --target template_release --objects core/object/object.cpp"
            " && bin/gai check",
        )

    def test_json_for_docs_change(self):
        result = self.run_gai("next", "--json", "AGENTS.md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["gate"], "none")
        self.assertEqual(payload["command"], "")

    def test_git_status_discovery(self):
        if shutil.which("git") is None:
            self.skipTest("git is not installed")
        git = ["git", "-C", str(self.tmp), "-c", "user.name=gai", "-c", "user.email=gai@example.com"]
        subprocess.run(git + ["init", "-q"], check=True, capture_output=True, text=True)
        subprocess.run(git + ["add", "-A"], check=True, capture_output=True, text=True)
        subprocess.run(git + ["commit", "-qm", "init"], check=True, capture_output=True, text=True)

        clean = self.run_gai("next", "--json")
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
        self.assertEqual(json.loads(clean.stdout)["gate"], "none")

        script = self.tmp / "game" / "probe.gd"
        script.write_text("extends Node\n", encoding="utf-8")
        result = self.run_gai("next", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["gate"], "script")
        self.assertEqual(payload["paths"], ["game/probe.gd"])

        subprocess.run(git + ["add", "-A"], check=True, capture_output=True, text=True)
        subprocess.run(git + ["commit", "-qm", "probe"], check=True, capture_output=True, text=True)
        script.unlink()
        deleted = self.run_gai("next", "--json")
        self.assertEqual(deleted.returncode, 0, deleted.stdout + deleted.stderr)
        payload = json.loads(deleted.stdout)
        self.assertEqual(payload["gate"], "check")
        self.assertEqual(payload["reasons"][0]["gate"], "check")
        self.assertEqual(payload["reasons"][0]["rule"], "game/**/*.gd (deleted)")

    def test_run_with_a_docs_change_exits_zero_without_an_engine(self):
        result = self.run_gai("next", "--run", "docs/gai/build.md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("next: gate none", result.stdout)
        self.assertNotIn("no engine", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
