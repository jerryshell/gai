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


ENGINE = built_engine() or os.environ.get("GAI_GODOT")


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
        if os.name == "posix":
            mode = (self.tmp / ".gai" / "agent.json").stat().st_mode & 0o777
            self.assertEqual(mode, 0o600)

        second = self.run_gai("agent", "start")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("already running", second.stdout)

        state = json.loads((self.tmp / ".gai" / "agent.json").read_text(encoding="utf-8"))
        idle = socket.create_connection(("127.0.0.1", state["port"]), timeout=5)
        try:
            status = self.run_gai("agent", "status")
            self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
        finally:
            idle.close()

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

        missing = self.run_gai("agent", "get", "/root/Nope")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("node not found", missing.stderr)

        unknown = self.run_gai("agent", "set", "/root/Main", "nope", "1")
        self.assertEqual(unknown.returncode, 1)
        self.assertIn("unknown property", unknown.stderr)

        wrong_type = self.run_gai("agent", "set", "/root/Main", "visible", "notabool")
        self.assertEqual(wrong_type.returncode, 1)
        self.assertIn("invalid value", wrong_type.stderr)

        stop = self.run_gai("agent", "stop")
        self.assertEqual(stop.returncode, 0, stop.stdout + stop.stderr)

    @unittest.skipUnless(ENGINE, "no source build with the agent bridge")
    def test_concurrent_start_keeps_one_game(self):
        env = dict(os.environ)
        env["GAI_GODOT"] = str(ENGINE)
        processes = [
            subprocess.Popen(
                [sys.executable, str(self.tmp / "bin" / "gai"), "agent", "start"],
                cwd=str(self.tmp),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            for _ in range(2)
        ]
        outputs = []
        for process in processes:
            out, err = process.communicate(timeout=40)
            outputs.append(out + err)
            self.assertEqual(process.returncode, 0, out + err)
        self.assertTrue(any("agent ready" in output for output in outputs), outputs)
        self.assertTrue(any("already running" in output for output in outputs), outputs)

    def test_stop_refuses_a_foreign_pid(self):
        sleep = shutil.which("sleep")
        if not sleep:
            self.skipTest("sleep is not available")
        process = subprocess.Popen([sleep, "30"])
        self.addCleanup(lambda: process.poll() is None and (process.kill(), process.wait()))
        state = {
            "pid": process.pid,
            "port": 1,
            "token": "not-the-agent",
            "engine": str(ENGINE),
            "starttime": "0",
        }
        (self.tmp / ".gai" / "agent.json").write_text(
            json.dumps(state) + "\n", encoding="utf-8"
        )
        result = self.run_gai("agent", "stop")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("not the agent", result.stdout)
        self.assertIsNone(process.poll())
        self.assertFalse((self.tmp / ".gai" / "agent.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=1)
