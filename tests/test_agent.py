#!/usr/bin/env python3
"""End-to-end tests for the agent bridge. Requires a source build with modules/gai_agent."""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
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
        self.assertIn("cannot parse value as bool", wrong_type.stderr)

        stop = self.run_gai("agent", "stop")
        self.assertEqual(stop.returncode, 0, stop.stdout + stop.stderr)

    @unittest.skipUnless(ENGINE, "no source build with the agent bridge")
    def test_autoloads(self):
        game = self.tmp / "game"
        (game / "autoloads").mkdir()
        (game / "autoloads" / "probe.gd").write_text(
            "extends Node\n\n\nfunc ping() -> String:\n\treturn \"pong\"\n",
            encoding="utf-8",
        )
        with (game / "project.godot").open("a", encoding="utf-8") as handle:
            handle.write('\n[autoload]\nProbe="*res://autoloads/probe.gd"\n')

        start = self.run_gai("agent", "start")
        self.assertEqual(start.returncode, 0, start.stdout + start.stderr)

        def call(method, params=None):
            result = self.run_gai("agent", "call", method, json.dumps(params or {}))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)

        autoloads = call("api.autoloads")["autoloads"]
        probe = next(item for item in autoloads if item["name"] == "Probe")
        self.assertEqual(probe["path"], "res://autoloads/probe.gd")
        self.assertIn("handle", probe)

        info = call("object.autoload", {"name": "Probe"})
        self.assertEqual(info["class"], "Node")
        self.assertEqual(info["path"], "/root/Probe")
        self.assertEqual(call("object.call", {"handle": info["handle"], "method": "ping", "args": []}), "pong")

        stop = self.run_gai("agent", "stop")
        self.assertEqual(stop.returncode, 0, stop.stdout + stop.stderr)

    @unittest.skipUnless(ENGINE, "no source build with the agent bridge")
    def test_batch_requests(self):
        start = self.run_gai("agent", "start")
        self.assertEqual(start.returncode, 0, start.stdout + start.stderr)
        state = json.loads((self.tmp / ".gai" / "agent.json").read_text(encoding="utf-8"))
        token = state["token"]

        def request(request_id, request_token=None):
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "ping",
                "params": {},
                "token": token if request_token is None else request_token,
            }

        batch = self.raw(json.dumps([request(1), request(2)]) + "\n")
        self.assertEqual([item["id"] for item in batch], [1, 2])
        self.assertTrue(batch[0]["result"]["pong"])

        unauthorized = self.raw(
            json.dumps([request(3), request(4, "wrong")]) + "\n"
        )
        self.assertEqual(unauthorized[1]["error"]["code"], -32001)

        empty = self.raw("[]\n")
        self.assertEqual(empty["error"]["code"], -32600)

        too_large = self.raw(json.dumps([request(index) for index in range(65)]) + "\n")
        self.assertEqual(too_large["error"]["code"], -32600)
        self.assertIn("Batch too large", too_large["error"]["message"])

        stop = self.run_gai("agent", "stop")
        self.assertEqual(stop.returncode, 0, stop.stdout + stop.stderr)

    @unittest.skipUnless(ENGINE, "no source build with the agent bridge")
    def test_multi_client_and_events(self):
        start = self.run_gai("agent", "start")
        self.assertEqual(start.returncode, 0, start.stdout + start.stderr)
        state = json.loads((self.tmp / ".gai" / "agent.json").read_text(encoding="utf-8"))

        watcher = socket.create_connection(("127.0.0.1", state["port"]), timeout=5)
        self.addCleanup(watcher.close)
        watcher.settimeout(5)

        def send(sock, request):
            sock.sendall((json.dumps(request) + "\n").encode("utf-8"))

        def read(sock):
            data = b""
            while b"\n" not in data:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                data += chunk
            return json.loads(data.split(b"\n", 1)[0].decode("utf-8"))

        send(
            watcher,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "event.subscribe",
                "params": {"path": "/root/Main/Title", "signal": "visibility_changed"},
                "token": state["token"],
            },
        )
        subscription = read(watcher)["result"]["subscription"]

        hidden = self.raw(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "node.set",
                    "params": {"path": "/root/Main/Title", "property": "visible", "value": False},
                    "token": state["token"],
                }
            )
            + "\n"
        )
        self.assertFalse(hidden["result"]["value"])

        event = read(watcher)
        self.assertEqual(event["method"], "event")
        self.assertEqual(event["params"]["subscription"], subscription)
        self.assertEqual(event["params"]["signal"], "visibility_changed")

        send(
            watcher,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "event.unsubscribe",
                "params": {"subscription": subscription},
                "token": state["token"],
            },
        )
        self.assertTrue(read(watcher)["result"]["removed"])

        restored = self.raw(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "node.set",
                    "params": {"path": "/root/Main/Title", "property": "visible", "value": True},
                    "token": state["token"],
                }
            )
            + "\n"
        )
        self.assertTrue(restored["result"]["value"])

        stop = self.run_gai("agent", "stop")
        self.assertEqual(stop.returncode, 0, stop.stdout + stop.stderr)

    @unittest.skipUnless(ENGINE, "no source build with the agent bridge")
    def test_event_replay(self):
        start = self.run_gai("agent", "start")
        self.assertEqual(start.returncode, 0, start.stdout + start.stderr)
        state = json.loads((self.tmp / ".gai" / "agent.json").read_text(encoding="utf-8"))
        token = state["token"]

        def connect():
            sock = socket.create_connection(("127.0.0.1", state["port"]), timeout=5)
            sock.settimeout(5)
            self.addCleanup(sock.close)
            return sock

        def send(sock, request_id, method, params):
            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
                "token": token,
            }
            sock.sendall((json.dumps(request) + "\n").encode("utf-8"))

        def read(sock):
            data = b""
            while b"\n" not in data:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                data += chunk
            return json.loads(data.split(b"\n", 1)[0].decode("utf-8"))

        watcher = connect()
        send(
            watcher,
            1,
            "event.subscribe",
            {"path": "/root/Main/Title", "signal": "visibility_changed"},
        )
        subscription = read(watcher)["result"]["subscription"]
        self.raw(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "node.set",
                    "params": {"path": "/root/Main/Title", "property": "visible", "value": False},
                    "token": token,
                }
            )
            + "\n"
        )
        event = read(watcher)
        seq = event["params"]["seq"]
        self.assertGreater(seq, 0)

        send(watcher, 2, "event.unsubscribe", {"subscription": subscription})
        self.assertTrue(read(watcher)["result"]["removed"])
        watcher.close()

        replay = connect()
        send(
            replay,
            3,
            "event.subscribe",
            {"path": "/root/Main/Title", "signal": "visibility_changed", "since": 0},
        )
        result = read(replay)["result"]
        self.assertFalse(result["lost"])
        self.assertTrue(
            any(item["seq"] == seq for item in result["replay"]),
            result["replay"],
        )

        send(
            replay,
            4,
            "event.subscribe",
            {"path": "/root/Main/Title", "signal": "visibility_changed", "since": seq},
        )
        result = read(replay)["result"]
        self.assertEqual(result["replay"], [])

        self.raw(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "node.set",
                    "params": {"path": "/root/Main/Title", "property": "visible", "value": True},
                    "token": token,
                }
            )
            + "\n"
        )
        replay.close()

        stop = self.run_gai("agent", "stop")
        self.assertEqual(stop.returncode, 0, stop.stdout + stop.stderr)

    @unittest.skipUnless(ENGINE, "no source build with the agent bridge")
    def test_editor_mode(self):
        start = self.run_gai("agent", "start", "--editor", timeout=60)
        self.assertEqual(start.returncode, 0, start.stdout + start.stderr)
        self.assertIn("agent ready", start.stdout)

        def call(method, params=None):
            result = self.run_gai("agent", "call", method, json.dumps(params or {}))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)

        singletons = call("api.singletons")
        self.assertIn("EditorInterface", [item["name"] for item in singletons["singletons"]])
        interface = call("object.singleton", {"name": "EditorInterface"})
        self.assertEqual(interface["class"], "EditorInterface")

        quit_attempt = self.run_gai("agent", "call", "run.quit", "{}")
        self.assertEqual(quit_attempt.returncode, 1)
        self.assertIn("editor mode", quit_attempt.stderr)
        input_attempt = self.run_gai("agent", "call", "input.action", '{"name":"ui_accept"}')
        self.assertEqual(input_attempt.returncode, 1)
        self.assertIn("editor mode", input_attempt.stderr)

        stop = self.run_gai("agent", "stop")
        self.assertEqual(stop.returncode, 0, stop.stdout + stop.stderr)

    @unittest.skipUnless(ENGINE, "no source build with the agent bridge")
    def test_capability_surface(self):
        start = self.run_gai("agent", "start")
        self.assertEqual(start.returncode, 0, start.stdout + start.stderr)

        def call(method, params=None):
            result = self.run_gai("agent", "call", method, json.dumps(params or {}))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)

        methods = call("api.methods")
        self.assertIn("classdb.classes", methods["methods"])
        self.assertIn("object.call", methods["methods"])

        singletons = call("api.singletons")
        self.assertIn("Engine", [item["name"] for item in singletons["singletons"]])

        classes = call("classdb.classes")["classes"]
        self.assertIn("Node2D", classes)
        self.assertIn("PhysicsServer3D", classes)

        node2d = call("classdb.class", {"name": "Node2D"})
        self.assertIn("position", [item["name"] for item in node2d["properties"]])

        tree = json.loads(self.run_gai("agent", "tree").stdout)
        handle = tree["root"]["handle"]
        self.assertTrue(call("object.get", {"handle": handle, "property": "visible"}))
        self.assertFalse(call("object.set", {"handle": handle, "property": "visible", "value": False}))
        self.assertFalse(call("object.get", {"handle": handle, "property": "visible"}))
        self.assertEqual(call("object.call", {"handle": handle, "method": "get_class", "args": []}), "Node2D")

        title = next(child for child in tree["root"]["children"] if child["name"] == "Title")
        self.assertEqual(
            call("object.set", {"handle": title["handle"], "property": "text", "value": "Color(1, 0, 0, 1)"}),
            "Color(1, 0, 0, 1)",
        )
        self.assertEqual(
            call("object.get", {"handle": title["handle"], "property": "text"}),
            "Color(1, 0, 0, 1)",
        )

        position = call("object.get", {"handle": handle, "property": "position"})
        self.assertTrue(position.startswith("Vector2("))
        call("object.set", {"handle": handle, "property": "position", "value": position})
        self.assertEqual(call("object.get", {"handle": handle, "property": "position"}), position)

        bad_handle = self.run_gai(
            "agent", "call", "object.set",
            json.dumps({"handle": handle, "property": "script", "value": {"$handle": "0"}}),
        )
        self.assertEqual(bad_handle.returncode, 1)
        self.assertIn("unknown handle", bad_handle.stderr)

        engine = call("object.singleton", {"name": "Engine"})
        version = call("object.call", {"handle": engine["handle"], "method": "get_version_info", "args": []})
        self.assertEqual(version["major"], 4)

        created = call("node.create", {"parent": "/root/Main", "type": "Node2D", "name": "Probe"})
        self.assertEqual(created["class"], "Node2D")
        tree = json.loads(self.run_gai("agent", "tree").stdout)
        self.assertTrue(any(child["name"] == "Probe" for child in tree["root"]["children"]))
        call("node.delete", {"path": "/root/Main/Probe"})

        renderer = call("object.singleton", {"name": "RenderingServer"})
        refused = self.run_gai("agent", "call", "object.free", json.dumps({"handle": renderer["handle"]}))
        self.assertEqual(refused.returncode, 1)
        self.assertIn("refusing", refused.stderr)
        refused_call = self.run_gai(
            "agent", "call", "object.call",
            json.dumps({"handle": renderer["handle"], "method": "free", "args": []}),
        )
        self.assertEqual(refused_call.returncode, 1)
        self.assertFalse(call("run.status")["paused"])

        rpc = call("classdb.instantiate", {"name": "JSONRPC"})
        response = call(
            "object.call",
            {"handle": rpc["handle"], "method": "make_response_error", "args": [1, "boom"]},
        )
        self.assertEqual(response["error"]["code"], 1)
        self.assertNotIn("$gai_error", response)
        call("object.free", {"handle": rpc["handle"]})

        left = call("node.create", {"parent": "/root/Main", "type": "Node2D", "name": "Left"})
        right = call("node.create", {"parent": "/root/Main", "type": "Node2D", "name": "Right"})
        call("node.reparent", {"path": left["path"], "parent": right["path"]})
        tree = json.loads(self.run_gai("agent", "tree").stdout)
        right_node = next(child for child in tree["root"]["children"] if child["name"] == "Right")
        self.assertTrue(any(child["name"] == "Left" for child in right_node["children"]))
        call("node.delete", {"path": right["path"]})

        missing = self.run_gai("agent", "call", "resource.load", '{"path":"res://missing.tres"}')
        self.assertEqual(missing.returncode, 1)

        gradient = call("classdb.instantiate", {"name": "Gradient"})
        self.assertEqual(gradient["class"], "Gradient")
        saved = call("resource.save", {"handle": gradient["handle"], "path": "user://probe.tres"})
        self.assertIn("saved", saved)
        loaded = call("resource.load", {"path": "user://probe.tres"})
        self.assertEqual(loaded["class"], "Gradient")
        call("object.free", {"handle": gradient["handle"]})
        call("object.free", {"handle": loaded["handle"]})

        self.assertEqual(call("project.get", {"key": "application/config/name"}), "my-game")
        self.assertFalse(call("run.status")["paused"])
        call("run.pause")
        self.assertTrue(call("run.status")["paused"])
        call("run.step", {"frames": 1})
        time.sleep(0.3)
        self.assertTrue(call("run.status")["paused"])
        call("run.resume")
        self.assertEqual(call("run.time_scale", {"scale": 0.5})["time_scale"], 0.5)
        call("run.time_scale", {"scale": 1.0})

        call("input.action", {"name": "ui_accept", "pressed": True})
        call("input.action", {"name": "ui_accept", "pressed": False})
        call("input.key", {"keycode": 32, "pressed": True})
        call("input.key", {"keycode": 32, "pressed": False})
        call("input.mouse", {"x": 10, "y": 20, "button": 1, "pressed": True})
        call("input.mouse", {"x": 10, "y": 20, "button": 1, "pressed": False})

        shot = self.run_gai("agent", "call", "render.screenshot", '{"path":"user://shot.png"}')
        self.assertEqual(shot.returncode, 1)
        self.assertIn("display", shot.stderr)

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
