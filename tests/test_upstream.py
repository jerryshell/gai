#!/usr/bin/env python3
"""End-to-end tests for the upstream tools in bin/gai."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GAI = Path(__file__).resolve().parent.parent / "bin" / "gai"

VERSION_BUMP = (
    'short_name = "godot"\nname = "Godot Engine"\nmajor = 4\nminor = 8\npatch = 0\n'
    'status = "stable"\nmodule_config = ""\nwebsite = "https://godotengine.org"\ndocs = "4.8"\n'
)


class Repo:
    def __init__(self, root: Path, env):
        self.root = root
        self.env = env

    def git(self, *args, check=True, cwd=None):
        result = subprocess.run(
            ["git", *map(str, args)],
            cwd=str(cwd or self.root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
        )
        if check and result.returncode != 0:
            raise AssertionError(
                f"git {' '.join(map(str, args))} failed\n{result.stdout}\n{result.stderr}"
            )
        return result

    def gai(self, *args):
        return subprocess.run(
            [sys.executable, str(self.root / "bin" / "gai"), *map(str, args)],
            cwd=str(self.root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
        )

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class UpstreamTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gai-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        env = dict(os.environ)
        env.update(
            {
                "GIT_AUTHOR_NAME": "gai test",
                "GIT_AUTHOR_EMAIL": "test@example.com",
                "GIT_COMMITTER_NAME": "gai test",
                "GIT_COMMITTER_EMAIL": "test@example.com",
            }
        )
        self.repo = Repo(self.tmp / "repo", env)
        self.repo.root.mkdir()
        (self.repo.root / "bin").mkdir()
        shutil.copy2(GAI, self.repo.root / "bin" / "gai")
        (self.repo.root / "bin" / "gai").chmod(0o755)

        self.repo.write("README.md", "# Godot Engine\n")
        self.repo.write(
            "version.py",
            'short_name = "godot"\nname = "Godot Engine"\nmajor = 4\nminor = 7\npatch = 2\nstatus = "stable"\n'
            'module_config = ""\nwebsite = "https://godotengine.org"\ndocs = "4.7"\n',
        )
        self.repo.write(".gitignore", "bin\n")
        self.repo.write("core/os/os.cpp", "// upstream\n")
        self.repo.write(".gai/version", "0.0.0-test\n")
        self.repo.git("init", "-q", "-b", "main")
        self.repo.git("add", "-A")
        self.repo.git("commit", "-q", "-m", "base")
        self.base = self.repo.git("rev-parse", "HEAD").stdout.strip()

        state = {
            "repo": "https://github.com/godotengine/godot.git",
            "tag": "4.7.2-stable",
            "commit": self.base,
            "merged_at": "2026-10-25",
            "owned_prefixes": [".gai/", "game/"],
            "owned_files": ["bin/gai"],
            "edited": [".gitignore", "README.md", "version.py"],
            "required": ["bin/gai", "game/project.godot"],
        }
        self.repo.write(".gai/upstream.json", json.dumps(state, indent=2) + "\n")
        self.repo.git("add", ".gai/upstream.json")
        self.repo.git("commit", "-q", "-m", "record upstream base")

        self.repo.write("README.md", "# test game\n")
        self.repo.write(
            "version.py",
            'short_name = "godot"\nname = "gai"\nmajor = 4\nminor = 7\npatch = 2\nstatus = "stable"\n'
            'module_config = ""\nwebsite = "https://github.com/jerryshell/gai"\ndocs = "4.7"\n',
        )
        self.repo.write(".gitignore", "bin\n!/bin/\n/bin/*\n!/bin/gai\n")
        self.repo.write("game/project.godot", "config_version=5\n")
        self.repo.write("game/scripts/main.gd", "extends Node2D\n")
        self.repo.git("add", "-A")
        self.repo.git("commit", "-q", "-m", "gai layer")

    def make_upstream(self, files: dict):
        bare = self.tmp / "upstream.git"
        work = self.tmp / "upstream-work"
        self.repo.git("clone", "-q", "--bare", str(self.repo.root), str(bare), cwd=self.tmp)
        self.repo.git("clone", "-q", str(bare), str(work), cwd=self.tmp)
        upstream = Repo(work, self.repo.env)
        upstream.git("checkout", "-q", "-b", "upstream-line", self.base)
        for relative, content in files.items():
            upstream.write(relative, content)
        upstream.git("add", "-A")
        upstream.git("commit", "-q", "-m", "upstream change")
        upstream.git("tag", "4.8.0-stable")
        upstream.git("push", "-q", "origin", "upstream-line", "--tags")
        self.repo.git("remote", "add", "upstream", str(bare))

    def state(self):
        return json.loads((self.repo.root / ".gai" / "upstream.json").read_text())

    def assert_layer_ok(self):
        result = self.repo.gai("upstream", "check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("layer: ok", result.stdout)

    def test_clean_merge_moves_the_base(self):
        self.make_upstream({"core/os/os.cpp": "// upstream change\n"})
        result = self.repo.gai("upstream", "merge", "4.8.0-stable")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        commit = self.repo.git("rev-parse", "4.8.0-stable^{commit}").stdout.strip()
        state = self.state()
        self.assertEqual(state["tag"], "4.8.0-stable")
        self.assertEqual(state["commit"], commit)
        self.assertEqual((self.repo.root / "core/os/os.cpp").read_text(), "// upstream change\n")
        self.assert_layer_ok()

    def test_readme_conflict_then_continue(self):
        self.make_upstream({"README.md": "# upstream readme\n"})
        result = self.repo.gai("upstream", "merge", "4.8.0-stable")
        self.assertEqual(result.returncode, 1)
        self.assertIn("README.md", result.stdout)
        self.assertIn("keep ours", result.stdout)

        self.repo.git("checkout", "--ours", "README.md")
        self.repo.git("add", "README.md")
        cont = self.repo.gai("upstream", "continue")
        self.assertEqual(cont.returncode, 0, cont.stdout + cont.stderr)

        self.assertEqual((self.repo.root / "README.md").read_text(), "# test game\n")
        self.assertEqual(self.state()["tag"], "4.8.0-stable")
        self.assert_layer_ok()

    def test_abort_restores_the_repo(self):
        self.make_upstream({"README.md": "# upstream readme\n"})
        result = self.repo.gai("upstream", "merge", "4.8.0-stable")
        self.assertEqual(result.returncode, 1)

        abort = self.repo.gai("upstream", "abort")
        self.assertEqual(abort.returncode, 0, abort.stdout + abort.stderr)
        self.assertTrue(self.repo.git("rev-parse", "--verify", "-q", "MERGE_HEAD", check=False).returncode != 0)
        self.assertEqual((self.repo.root / "README.md").read_text(), "# test game\n")

    def test_version_bump_is_resolved_automatically(self):
        self.make_upstream({"version.py": VERSION_BUMP})
        result = self.repo.gai("upstream", "merge", "4.8.0-stable")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("resolved version.py", result.stdout)

        text = (self.repo.root / "version.py").read_text()
        self.assertIn('name = "gai"', text)
        self.assertIn('website = "https://github.com/jerryshell/gai"', text)
        self.assertIn("minor = 8", text)
        self.assertIn('docs = "4.8"', text)
        self.assert_layer_ok()

    def test_version_bump_and_readme_conflict(self):
        self.make_upstream({"version.py": VERSION_BUMP, "README.md": "# upstream readme\n"})
        result = self.repo.gai("upstream", "merge", "4.8.0-stable")
        self.assertEqual(result.returncode, 1)
        self.assertIn("resolved version.py", result.stdout)
        self.assertIn("README.md", result.stdout)

        self.repo.git("checkout", "--ours", "README.md")
        self.repo.git("add", "README.md")
        cont = self.repo.gai("upstream", "continue")
        self.assertEqual(cont.returncode, 0, cont.stdout + cont.stderr)

        text = (self.repo.root / "version.py").read_text()
        self.assertIn('name = "gai"', text)
        self.assertIn("minor = 8", text)
        self.assert_layer_ok()

    def test_deleting_a_required_file_fails(self):
        self.repo.git("rm", "game/project.godot")
        self.repo.git("commit", "-q", "-m", "delete required")
        result = self.repo.gai("upstream", "check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("game/project.godot", result.stdout)
        self.assertIn("required files are missing", result.stdout)

    def test_merge_refuses_a_dirty_tree(self):
        self.make_upstream({"core/os/os.cpp": "// upstream change\n"})
        self.repo.write("README.md", "# local edit\n")
        result = self.repo.gai("upstream", "merge", "4.8.0-stable")
        self.assertEqual(result.returncode, 1)
        self.assertIn("uncommitted", (result.stdout + result.stderr).lower())

    def test_edit_outside_the_layer_fails(self):
        self.repo.write("core/os/os.cpp", "// local change\n")
        self.repo.git("add", "-A")
        self.repo.git("commit", "-q", "-m", "edit engine")
        result = self.repo.gai("upstream", "check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("M core/os/os.cpp", result.stdout)

    def test_owned_file_is_allowed(self):
        self.repo.write("game/scripts/player.gd", "extends Node2D\n")
        self.repo.git("add", "-A")
        self.repo.git("commit", "-q", "-m", "add game script")
        self.assert_layer_ok()


if __name__ == "__main__":
    unittest.main(verbosity=1)
