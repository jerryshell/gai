#!/usr/bin/env python3
"""Tests for the MCP stdio adapter. These do not need an engine."""

import base64
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))

import gai_mcp

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z3ZkAAAAASUVORK5CYII="
)


class FakeRunner:
    def __init__(
        self,
        test_payload=None,
        test_code=0,
        check_output="check: ok\n",
        check_code=0,
    ):
        self.test_payload = test_payload or {
            "tests": 2,
            "passed": 2,
            "failed": 0,
            "pending": 0,
            "results": [],
        }
        self.test_code = test_code
        self.check_output = check_output
        self.check_code = check_code
        self.commands = []

    def __call__(self, command, timeout):
        self.commands.append((command, timeout))
        if command[0] == "test":
            return {
                "returncode": self.test_code,
                "stdout": json.dumps(self.test_payload) + "\n",
                "stderr": "",
            }
        return {
            "returncode": self.check_code,
            "stdout": self.check_output,
            "stderr": "",
        }


class FakeEventSource:
    def __init__(self):
        self.callback = None
        self.calls = []

    def set_callback(self, callback):
        self.callback = callback

    def subscribe(self, path=None, handle=None, signal=None, since=None):
        self.calls.append(("subscribe", path, handle, signal, since))
        if self.callback is not None:
            self.callback(
                {
                    "subscription": 1,
                    "signal": signal,
                    "path": path,
                    "args": [],
                }
            )
        return {"subscription": 1, "signal": signal, "path": path}

    def unsubscribe(self, subscription):
        self.calls.append(("unsubscribe", subscription))
        return {"subscription": subscription, "removed": True}


class FakeBridge:
    def __init__(self):
        self.calls = []

    def __call__(self, method, params):
        self.calls.append((method, params))
        if method == "ping":
            return {"pong": True, "engine": "test"}
        if method == "api.methods":
            return ["ping", "scene.tree", "node.get", "node.set"]
        if method == "scene.tree":
            return {"name": "Main", "children": []}
        if method == "node.get":
            return {"path": params["path"], "visible": True}
        if method == "node.set":
            return {
                "path": params["path"],
                "property": params["property"],
                "value": params["value"],
            }
        if method == "bad":
            return {"$gai_error": "bad bridge call"}
        if method == "render.screenshot":
            path = Path(params["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(PNG)
            return {"path": str(path), "width": 1, "height": 1}
        raise RuntimeError("unknown bridge method")


class McpTest(unittest.TestCase):
    def setUp(self):
        self.runtime = Path(tempfile.mkdtemp(prefix="gai-mcp-"))
        self.addCleanup(shutil.rmtree, self.runtime, ignore_errors=True)

    def request(self, request_id, method, params=None):
        message = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        return message

    def call_tool(self, name, arguments):
        return self.request(
            2,
            "tools/call",
            {"name": name, "arguments": arguments},
        )

    def run_mcp(self, messages, runner=None, event_source=None):
        runner = runner or FakeRunner()
        self.last_runner = runner
        stdin = io.StringIO()
        for message in messages:
            stdin.write(message if isinstance(message, str) else json.dumps(message))
            stdin.write("\n")
        stdin.seek(0)
        stdout = io.StringIO()
        bridge = FakeBridge()
        code = gai_mcp.serve(
            bridge,
            stdin,
            stdout,
            root=ROOT,
            project=ROOT / "game",
            runtime=self.runtime,
            version="test",
            runner=runner,
            command_timeout=12.0,
            event_source=event_source,
        )
        self.assertEqual(code, 0)
        self.last_stdout = stdout.getvalue()
        responses = [json.loads(line) for line in self.last_stdout.splitlines()]
        return responses, bridge

    def test_initialize_and_tools_list(self):
        responses, _ = self.run_mcp(
            [
                self.request(
                    1,
                    "initialize",
                    {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1"},
                    },
                ),
                self.request(2, "tools/list"),
            ]
        )
        initialized = responses[0]["result"]
        self.assertEqual(initialized["serverInfo"]["name"], "gai")
        self.assertEqual(initialized["protocolVersion"], "2025-06-18")
        names = {tool["name"] for tool in responses[1]["result"]["tools"]}
        self.assertIn("gai_scene_tree", names)
        self.assertIn("gai_call", names)
        self.assertIn("gai_screenshot", names)
        self.assertIn("gai_test", names)
        self.assertIn("gai_check", names)
        self.assertIn("gai_subscribe", names)
        self.assertIn("gai_unsubscribe", names)

    def test_scene_tree(self):
        responses, _ = self.run_mcp(
            [self.call_tool("gai_scene_tree", {})]
        )
        result = responses[0]["result"]
        self.assertFalse(result["isError"])
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["name"], "Main")

    def test_call_forwards_to_bridge(self):
        responses, bridge = self.run_mcp(
            [
                self.call_tool(
                    "gai_call",
                    {"method": "ping", "params": {}},
                )
            ]
        )
        self.assertFalse(responses[0]["result"]["isError"])
        self.assertIn(("ping", {}), bridge.calls)

    def test_node_set_keeps_json_value(self):
        responses, bridge = self.run_mcp(
            [
                self.call_tool(
                    "gai_node_set",
                    {"path": "/root/Main", "property": "visible", "value": False},
                )
            ]
        )
        self.assertFalse(responses[0]["result"]["isError"])
        self.assertEqual(bridge.calls[-1][0], "node.set")
        self.assertIs(bridge.calls[-1][1]["value"], False)

    def test_read_file(self):
        responses, _ = self.run_mcp(
            [self.call_tool("gai_read_file", {"path": "project.godot"})]
        )
        result = responses[0]["result"]
        self.assertFalse(result["isError"])
        payload = json.loads(result["content"][0]["text"])
        self.assertIn("run/main_scene", payload["text"])

    def test_read_file_rejects_traversal(self):
        responses, _ = self.run_mcp(
            [self.call_tool("gai_read_file", {"path": "../version.py"})]
        )
        result = responses[0]["result"]
        self.assertTrue(result["isError"])
        self.assertIn("escapes", result["content"][0]["text"])

    def test_read_file_rejects_bridge_token(self):
        responses, _ = self.run_mcp(
            [self.call_tool("gai_read_file", {"path": ".gai/agent.json"})]
        )
        result = responses[0]["result"]
        self.assertTrue(result["isError"])
        self.assertIn("token", result["content"][0]["text"])

    def test_resources(self):
        responses, _ = self.run_mcp(
            [
                self.request(1, "resources/list"),
                self.request(2, "resources/read", {"uri": "gai://project.godot"}),
                self.request(3, "resources/read", {"uri": "gai://missing"}),
            ]
        )
        uris = {resource["uri"] for resource in responses[0]["result"]["resources"]}
        self.assertIn("gai://docs/testing", uris)
        contents = responses[1]["result"]["contents"][0]
        self.assertIn("run/main_scene", contents["text"])
        self.assertEqual(responses[2]["error"]["code"], -32002)

    def test_screenshot(self):
        responses, _ = self.run_mcp([self.call_tool("gai_screenshot", {})])
        result = responses[0]["result"]
        self.assertFalse(result["isError"])
        image = result["content"][0]
        self.assertEqual(image["type"], "image")
        self.assertEqual(image["mimeType"], "image/png")
        data = base64.b64decode(image["data"])
        self.assertTrue(data.startswith(b"\x89PNG"))
        self.assertEqual(list(self.runtime.glob("screenshots/*.png")), [])

    def test_gai_test_success_and_filter(self):
        runner = FakeRunner(
            test_payload={"tests": 2, "passed": 2, "failed": 0, "pending": 0, "results": []}
        )
        responses, _ = self.run_mcp(
            [self.call_tool("gai_test", {"filter": "player"})],
            runner,
        )
        result = responses[0]["result"]
        self.assertFalse(result["isError"])
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["exit_code"], 0)
        self.assertEqual(payload["result"]["passed"], 2)
        self.assertEqual(runner.commands[0][0], ["test", "--json", "--filter", "player"])
        self.assertEqual(runner.commands[0][1], 12.0)

    def test_gai_test_failure(self):
        runner = FakeRunner(
            test_payload={
                "tests": 1,
                "passed": 0,
                "failed": 1,
                "pending": 0,
                "results": [{"status": "fail"}],
            },
            test_code=1,
        )
        responses, _ = self.run_mcp([self.call_tool("gai_test", {})], runner)
        result = responses[0]["result"]
        self.assertTrue(result["isError"])
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["result"]["failed"], 1)

    def test_gai_check(self):
        runner = FakeRunner(check_output="check: ok\n")
        responses, _ = self.run_mcp([self.call_tool("gai_check", {})], runner)
        result = responses[0]["result"]
        self.assertFalse(result["isError"])
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["exit_code"], 0)
        self.assertIn("check: ok", payload["output"])
        self.assertEqual(runner.commands[0][0], ["check"])

    def test_gai_check_failure(self):
        runner = FakeRunner(check_output="check: failed\n", check_code=1)
        responses, _ = self.run_mcp([self.call_tool("gai_check", {})], runner)
        result = responses[0]["result"]
        self.assertTrue(result["isError"])
        payload = json.loads(result["content"][0]["text"])
        self.assertIn("check: failed", payload["output"])

    def test_event_forwarding(self):
        source = FakeEventSource()
        responses, _ = self.run_mcp(
            [
                self.call_tool(
                    "gai_subscribe",
                    {"path": "/root/Main", "signal": "ready", "since": 5},
                )
            ],
            event_source=source,
        )
        self.assertEqual(source.calls, [("subscribe", "/root/Main", None, "ready", 5)])
        notifications = [
            message
            for message in responses
            if message.get("method") == "notifications/message"
        ]
        self.assertEqual(len(notifications), 1)
        event = notifications[0]["params"]["data"]["event"]
        self.assertEqual(event["signal"], "ready")
        response = next(message for message in responses if message.get("id") == 2)
        self.assertFalse(response["result"]["isError"])
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(payload["subscription"], 1)

    def test_event_unsubscribe(self):
        source = FakeEventSource()
        responses, _ = self.run_mcp(
            [self.call_tool("gai_unsubscribe", {"subscription": 1})],
            event_source=source,
        )
        self.assertEqual(source.calls, [("unsubscribe", 1)])
        self.assertFalse(responses[0]["result"]["isError"])

    def test_batch_and_unknown_method(self):
        responses, _ = self.run_mcp(
            [
                [
                    self.request(1, "ping"),
                    self.request(2, "nope"),
                ]
            ]
        )
        batch = responses[0]
        self.assertEqual(batch[0]["result"], {})
        self.assertEqual(batch[1]["error"]["code"], -32601)

    def test_tool_and_bridge_errors(self):
        responses, _ = self.run_mcp(
            [
                self.call_tool("nope", {}),
                self.call_tool("gai_call", {"method": "bad", "params": {}}),
                self.call_tool("gai_call", {"method": "ping", "params": []}),
            ]
        )
        for response in responses:
            self.assertTrue(response["result"]["isError"])
        self.assertIn("unknown tool", responses[0]["result"]["content"][0]["text"])
        self.assertIn("bad bridge call", responses[1]["result"]["content"][0]["text"])

    def test_parse_error_and_notification(self):
        responses, _ = self.run_mcp(
            [
                "not json",
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "method": "nope"},
            ]
        )
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["error"]["code"], -32700)


if __name__ == "__main__":
    unittest.main(verbosity=1)
