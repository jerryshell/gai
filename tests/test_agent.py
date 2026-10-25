#!/usr/bin/env python3
"""End-to-end tests for the agent bridge. Requires a source build with modules/gai_agent."""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def built_engine():
    for path in sorted((ROOT / "bin").glob("godot.*.editor.*")):
        if ".console." in path.name or path.name.endswith(".debug"):
            continue
        if path.is_file():
            return path
    return None


ENGINE = os.environ.get("GAI_GODOT") or built_engine()


class AgentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gai-agent-"))
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
        self.env = dict(os.environ)
        self.env["GAI_GODOT"] = str(ENGINE)
        self.addCleanup(self.stop_agent)

    def stop_agent(self):
        self.run_gai("agent", "stop")

    def raw(self, payload: str):
        state = json.loads((self.tmp / ".gai" / "agent.json").read_text(encoding="utf-8"))
        with socket.create_connection(("127.0.0.1", state["port"]), timeout=5) as sock:
            sock.sendall(payload.encode("utf-8"))
            data = b""
            while b"\n" not in data:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                data += chunk
        return json.loads(data.split(b"\n", 1)[0].decode("utf-8"))

    def run_gai(self, *args, timeout=30):
        return subprocess.run(
            [sys.executable, str(self.tmp / "bin" / "gai"), *map(str, args)],
            cwd=str(self.tmp),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            timeout=timeout,
        )

    @unittest.skipUnless(ENGINE, "no source build with the agent bridge")
    def test_scene_tree_get_set(self):
        start = self.run_gai("agent", "start")
        self.assertEqual(start.returncode, 0, start.stdout + start.stderr)
        self.assertIn("agent ready", start.stdout)

        unauthorized = self.raw(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "scene.tree", "params": {}, "token": "wrong"}) + "\n"
        )
        self.assertEqual(unauthorized["error"]["code"], -32001)

        missing_token = self.raw(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "scene.tree", "params": {}}) + "\n"
        )
        self.assertEqual(missing_token["error"]["code"], -32001)

        malformed = self.raw("not json\n")
        self.assertEqual(malformed["error"]["code"], -32700)

        batch = self.raw("[]\n")
        self.assertEqual(batch["error"]["code"], -32600)

        state = json.loads((self.tmp / ".gai" / "agent.json").read_text(encoding="utf-8"))
        unknown = self.raw(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "nope", "params": {}, "token": state["token"]}) + "\n"
        )
        self.assertEqual(unknown["error"]["code"], -32601)

        tree = self.run_gai("agent", "tree")
        self.assertEqual(tree.returncode, 0, tree.stdout + tree.stderr)
        data = json.loads(tree.stdout)
        self.assertEqual(data["root"]["name"], "Main")
        self.assertEqual(data["root"]["type"], "Node2D")
        children = [child["name"] for child in data["root"]["children"]]
        self.assertIn("Title", children)

        get = self.run_gai("agent", "get", "/root/Main", "--property", "visible")
        self.assertEqual(get.returncode, 0, get.stdout + get.stderr)
        self.assertTrue(json.loads(get.stdout)["properties"]["visible"])

        set_result = self.run_gai("agent", "set", "/root/Main", "visible", "false")
        self.assertEqual(set_result.returncode, 0, set_result.stdout + set_result.stderr)
        self.assertFalse(json.loads(set_result.stdout)["value"])

        get_again = self.run_gai("agent", "get", "/root/Main", "--property", "visible")
        self.assertFalse(json.loads(get_again.stdout)["properties"]["visible"])

        stop = self.run_gai("agent", "stop")
        self.assertEqual(stop.returncode, 0, stop.stdout + stop.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
