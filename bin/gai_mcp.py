#!/usr/bin/env python3
"""Serve the gai agent bridge over the Model Context Protocol (stdio).

This is an adapter, not an engine feature. It speaks MCP on stdin/stdout and
forwards tool calls to the existing local JSON-RPC bridge. Nothing listens on a
network port.
"""

from __future__ import annotations

import base64
import json
import socket
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Callable

PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")
MAX_READ_BYTES = 1024 * 1024


class BridgeConnection:
    """Persistent JSON-RPC connection to the local gai bridge."""

    def __init__(self, port: int, token: str, timeout: float = 30.0) -> None:
        self.sock = socket.create_connection(("127.0.0.1", int(port)), timeout=5)
        self.sock.settimeout(None)
        self.stream = self.sock.makefile("r", encoding="utf-8", newline="\n")
        self.token = token
        self.timeout = timeout
        self._lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._pending = {}
        self._next_id = 1
        self._callback = None
        self._closed = False
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def set_callback(self, callback) -> None:
        self._callback = callback

    def call(self, method: str, params: dict):
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            waiter = {"event": threading.Event(), "response": None}
            self._pending[request_id] = waiter
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
            "token": self.token,
        }
        try:
            with self._send_lock:
                self.sock.sendall(
                    (json.dumps(request, ensure_ascii=True) + "\n").encode("utf-8")
                )
        except OSError as exc:
            with self._lock:
                self._pending.pop(request_id, None)
            raise RuntimeError(f"bridge send failed: {exc}") from exc
        if not waiter["event"].wait(self.timeout):
            with self._lock:
                self._pending.pop(request_id, None)
            raise TimeoutError(f"bridge call timed out after {self.timeout}s")
        response = waiter["response"]
        if response is None:
            raise RuntimeError("bridge connection closed")
        if "error" in response:
            raise RuntimeError(str(response["error"].get("message", "bridge error")))
        return response.get("result")

    def subscribe(self, path=None, handle=None, signal=None, since=None):
        params = {"signal": signal}
        if handle is not None:
            params["handle"] = handle
        elif path is not None:
            params["path"] = path
        if since is not None:
            params["since"] = int(since)
        return self.call("event.subscribe", params)

    def unsubscribe(self, subscription: int):
        return self.call("event.unsubscribe", {"subscription": subscription})

    def _read(self) -> None:
        try:
            for line in self.stream:
                text = line.strip()
                if not text:
                    continue
                try:
                    message = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if "id" in message:
                    with self._lock:
                        waiter = self._pending.pop(message["id"], None)
                    if waiter is not None:
                        waiter["response"] = message
                        waiter["event"].set()
                elif message.get("method") == "event":
                    callback = self._callback
                    if callback is not None:
                        try:
                            callback(message.get("params", {}))
                        except Exception:
                            log(traceback.format_exc())
        except OSError:
            pass
        finally:
            with self._lock:
                pending = self._pending
                self._pending = {}
            for waiter in pending.values():
                waiter["response"] = None
                waiter["event"].set()
            try:
                self.stream.close()
            except OSError:
                pass

    def close(self) -> None:
        self._closed = True
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class ToolError(Exception):
    pass


class ResourceNotFound(Exception):
    pass


class MethodNotFound(Exception):
    pass


class ImageResult:
    def __init__(self, data: str, text: str) -> None:
        self.data = data
        self.text = text


class ToolFailure:
    def __init__(self, value: Any) -> None:
        self.value = value


def log(message: str) -> None:
    print(f"gai-mcp: {message}", file=sys.stderr, flush=True)


def _schema(properties: dict, required: tuple = ()) -> dict:
    schema = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = list(required)
    return schema


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def _result_text(value: Any) -> dict:
    return {"content": [{"type": "text", "text": _text(value)}], "isError": False}


def _result_error(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def _last_json(text: str) -> Any:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        return value
    return None


def _error(request_id: Any, code: int, message: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _write(stream, payload: Any) -> None:
    stream.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), default=str) + "\n")
    stream.flush()


class Server:
    def __init__(
        self,
        bridge: Callable[[str, dict], Any],
        root: Path,
        project: Path,
        runtime: Path | None = None,
        version: str = "unknown",
        runner: Callable[[list[str], float], dict] | None = None,
        command_timeout: float = 300.0,
        event_source=None,
    ) -> None:
        self.bridge = bridge
        self.root = Path(root)
        self.project = Path(project)
        self.runtime = Path(runtime) if runtime is not None else self.project / ".gai"
        self.version = version
        self.runner = runner
        self.command_timeout = command_timeout
        self.event_source = event_source
        self.stdout = None
        self.write_lock = threading.Lock()
        self.stopped = False

    def tool_specs(self) -> list[dict]:
        return [
            {
                "name": "gai_status",
                "description": "Return the gai bridge status, engine, and project paths.",
                "inputSchema": _schema({}),
            },
            {
                "name": "gai_methods",
                "description": (
                    "List every method the gai bridge exposes. Call gai_call for a "
                    "method that has no dedicated tool."
                ),
                "inputSchema": _schema({}),
            },
            {
                "name": "gai_scene_tree",
                "description": "Return the live scene tree of the running game or editor.",
                "inputSchema": _schema({}),
            },
            {
                "name": "gai_node_get",
                "description": "Read a node's properties by path, for example /root/Main.",
                "inputSchema": _schema(
                    {
                        "path": {"type": "string"},
                        "properties": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional property names.",
                        },
                    },
                    ("path",),
                ),
            },
            {
                "name": "gai_node_set",
                "description": (
                    "Set one property on a node by path. value can be JSON or Godot "
                    "text such as Vector2(10, 20)."
                ),
                "inputSchema": _schema(
                    {
                        "path": {"type": "string"},
                        "property": {"type": "string"},
                        "value": {},
                    },
                    ("path", "property", "value"),
                ),
            },
            {
                "name": "gai_call",
                "description": (
                    "Call any gai bridge method with JSON params. Use gai_methods to "
                    "discover method names. This reaches the full engine surface."
                ),
                "inputSchema": _schema(
                    {
                        "method": {"type": "string"},
                        "params": {
                            "type": "object",
                            "additionalProperties": True,
                            "description": "JSON params for the bridge method.",
                        },
                    },
                    ("method",),
                ),
            },
            {
                "name": "gai_read_file",
                "description": "Read a UTF-8 file under the game project (max 1 MiB).",
                "inputSchema": _schema({"path": {"type": "string"}}, ("path",)),
            },
            {
                "name": "gai_screenshot",
                "description": (
                    "Capture the running game to a PNG image. The game must run "
                    "with a display."
                ),
                "inputSchema": _schema({}),
            },
            {
                "name": "gai_test",
                "description": (
                    "Run the game tests headlessly and return the JSON summary. "
                    "An optional filter matches file::name."
                ),
                "inputSchema": _schema(
                    {
                        "filter": {
                            "type": "string",
                            "description": "Only tests whose file::name contains this text.",
                        }
                    }
                ),
            },
            {
                "name": "gai_check",
                "description": (
                    "Run the full game check: import, parse, main scene, and tests. "
                    "This can take longer than a bridge call."
                ),
                "inputSchema": _schema({}),
            },
            {
                "name": "gai_subscribe",
                "description": (
                    "Subscribe to a bridge signal. Events are forwarded as MCP "
                    "logging notifications with logger gai and data.type gai.event."
                ),
                "inputSchema": _schema(
                    {
                        "path": {"type": "string"},
                        "handle": {"type": "string"},
                        "signal": {"type": "string"},
                        "since": {
                            "type": "integer",
                            "description": "Replay events with a seq greater than this value.",
                        },
                    },
                    ("signal",),
                ),
            },
            {
                "name": "gai_unsubscribe",
                "description": "Remove a bridge signal subscription.",
                "inputSchema": _schema(
                    {"subscription": {"type": "integer"}},
                    ("subscription",),
                ),
            },
        ]

    def resource_specs(self) -> list[dict]:
        return [
            {
                "uri": "gai://project.godot",
                "name": "project.godot",
                "description": "The game's project settings.",
                "mimeType": "text/plain",
            },
            {
                "uri": "gai://docs/testing",
                "name": "Game testing guide",
                "description": "How to write and run game tests.",
                "mimeType": "text/markdown",
            },
            {
                "uri": "gai://docs/agent-bridge",
                "name": "Agent bridge",
                "description": "The bridge method surface and handle model.",
                "mimeType": "text/markdown",
            },
            {
                "uri": "gai://logs/check",
                "name": "check.log",
                "description": "The last check log.",
                "mimeType": "text/plain",
            },
            {
                "uri": "gai://logs/test",
                "name": "test.log",
                "description": "The last test log.",
                "mimeType": "text/plain",
            },
        ]

    def initialize(self, params: Any) -> dict:
        requested = ""
        if isinstance(params, dict):
            requested = params.get("protocolVersion", "")
        version = requested if requested in SUPPORTED_VERSIONS else PROTOCOL_VERSION
        return {
            "protocolVersion": version,
            "capabilities": {
                "tools": {},
                "resources": {},
                "logging": {},
            },
            "serverInfo": {"name": "gai", "version": self.version},
            "instructions": (
                "Start with gai_status, gai_scene_tree, and gai_node_get. Use "
                "gai_methods then gai_call for anything not covered by a tool. "
                "gai_screenshot needs a game started with --display. "
                "Use gai_subscribe for bridge events."
            ),
        }

    def tools_call(self, params: Any) -> dict:
        if not isinstance(params, dict):
            raise ToolError("tools/call params must be an object")
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise ToolError("tool name is required")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ToolError("arguments must be an object")
        value = self.call_tool(name, arguments)
        if isinstance(value, ImageResult):
            content = [{"type": "image", "data": value.data, "mimeType": "image/png"}]
            if value.text:
                content.append({"type": "text", "text": value.text})
            return {"content": content, "isError": False}
        if isinstance(value, ToolFailure):
            return {"content": [{"type": "text", "text": _text(value.value)}], "isError": True}
        return _result_text(value)

    def call_tool(self, name: str, arguments: dict) -> Any:
        if name == "gai_status":
            return {
                "project": str(self.project),
                "root": str(self.root),
                "runtime": str(self.runtime),
                "version": self.version,
                "ping": self._bridge("ping", {}),
            }
        if name == "gai_methods":
            return self._bridge("api.methods", {})
        if name == "gai_scene_tree":
            return self._bridge("scene.tree", {})
        if name == "gai_node_get":
            path = self._required_string(arguments, "path")
            params: dict = {"path": path}
            if "properties" in arguments:
                properties = arguments["properties"]
                if not isinstance(properties, list) or not all(
                    isinstance(item, str) for item in properties
                ):
                    raise ToolError("properties must be an array of strings")
                params["properties"] = properties
            return self._bridge("node.get", params)
        if name == "gai_node_set":
            path = self._required_string(arguments, "path")
            property_name = self._required_string(arguments, "property")
            if "value" not in arguments:
                raise ToolError("value is required")
            return self._bridge(
                "node.set",
                {
                    "path": path,
                    "property": property_name,
                    "value": arguments["value"],
                },
            )
        if name == "gai_call":
            method = self._required_string(arguments, "method")
            params_value = arguments.get("params", {})
            if params_value is None:
                params_value = {}
            if not isinstance(params_value, dict):
                raise ToolError("params must be an object")
            return self._bridge(method, params_value)
        if name == "gai_read_file":
            return self.read_file(self._required_string(arguments, "path"))
        if name == "gai_screenshot":
            return self.screenshot()
        if name == "gai_test":
            return self.run_test(arguments)
        if name == "gai_check":
            return self.run_check(arguments)
        if name == "gai_subscribe":
            return self.subscribe_tool(arguments)
        if name == "gai_unsubscribe":
            return self.unsubscribe_tool(arguments)
        raise ToolError(f"unknown tool: {name}")

    def read_file(self, relative_path: str) -> dict:
        relative = Path(relative_path)
        if relative.is_absolute():
            raise ToolError("path must be relative to the project")
        target = (self.project / relative).resolve()
        try:
            target.relative_to(self.project.resolve())
        except ValueError:
            raise ToolError("path escapes the project")
        if target == (self.project / ".gai" / "agent.json").resolve():
            raise ToolError("the bridge token file is not readable")
        if not target.is_file():
            raise ToolError(f"file not found: {relative_path}")
        if target.stat().st_size > MAX_READ_BYTES:
            raise ToolError(f"file is larger than {MAX_READ_BYTES} bytes")
        return {
            "path": relative.as_posix(),
            "text": target.read_text(encoding="utf-8", errors="replace"),
        }

    def screenshot(self) -> ImageResult:
        output_dir = self.runtime / "screenshots"
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"mcp-{int(time.time() * 1000)}.png"
        result = self._bridge("render.screenshot", {"path": str(path)})
        saved = path
        if isinstance(result, dict) and result.get("path"):
            saved = Path(str(result["path"]))
            if not saved.is_absolute():
                saved = self.project / saved
        if not saved.is_file():
            raise ToolError(f"screenshot failed: {_text(result)}")
        data = saved.read_bytes()
        if saved != path:
            try:
                saved.unlink()
            except OSError:
                pass
        else:
            try:
                path.unlink()
            except OSError:
                pass
        width = result.get("width", "?") if isinstance(result, dict) else "?"
        height = result.get("height", "?") if isinstance(result, dict) else "?"
        return ImageResult(
            base64.b64encode(data).decode("ascii"),
            f"{width}x{height} PNG",
        )

    def subscribe_tool(self, arguments: dict) -> Any:
        if self.event_source is None:
            raise ToolError("event forwarding is not configured")
        signal = self._required_string(arguments, "signal")
        path = arguments.get("path")
        handle = arguments.get("handle")
        if path is not None and not isinstance(path, str):
            raise ToolError("path must be a string")
        if handle is not None and not isinstance(handle, str):
            raise ToolError("handle must be a string")
        if bool(path) == bool(handle):
            raise ToolError("pass exactly one of path or handle")
        since = arguments.get("since")
        if since is not None and (isinstance(since, bool) or not isinstance(since, int)):
            raise ToolError("since must be an integer")
        return self.event_source.subscribe(
            path=path, handle=handle, signal=signal, since=since
        )

    def unsubscribe_tool(self, arguments: dict) -> Any:
        if self.event_source is None:
            raise ToolError("event forwarding is not configured")
        subscription = arguments.get("subscription")
        if isinstance(subscription, bool) or not isinstance(subscription, int):
            raise ToolError("subscription must be an integer")
        return self.event_source.unsubscribe(subscription)

    def emit_event(self, params: dict) -> None:
        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/message",
            "params": {
                "level": "info",
                "logger": "gai",
                "data": {"type": "gai.event", "event": params},
            },
        }
        self.write(notification)

    def write(self, payload: Any) -> None:
        with self.write_lock:
            if self.stdout is not None:
                _write(self.stdout, payload)

    def run_test(self, arguments: dict) -> Any:
        if self.runner is None:
            raise ToolError("the test runner is not configured")
        command = ["test", "--json"]
        filter_value = arguments.get("filter", "")
        if filter_value:
            if not isinstance(filter_value, str):
                raise ToolError("filter must be a string")
            command.extend(["--filter", filter_value])
        result = self.runner(command, self.command_timeout)
        stdout = str(result.get("stdout", ""))
        summary = _last_json(stdout)
        if not isinstance(summary, dict):
            detail = str(result.get("error") or result.get("stderr") or stdout[-2000:])
            raise ToolError(f"the test command did not return JSON: {detail}")
        payload = {"exit_code": result.get("returncode"), "result": summary}
        failed = int(result.get("returncode") or 0) != 0 or int(summary.get("failed", 0)) > 0
        return ToolFailure(payload) if failed else payload

    def run_check(self, arguments: dict) -> Any:
        del arguments
        if self.runner is None:
            raise ToolError("the check runner is not configured")
        result = self.runner(["check"], self.command_timeout)
        output = str(result.get("stdout", "")) + str(result.get("stderr", ""))
        if result.get("error"):
            output += "\n" + str(result["error"])
        output = output.strip()
        if len(output) > 100_000:
            output = output[:100_000] + "\n... truncated"
        payload = {"exit_code": result.get("returncode"), "output": output}
        return ToolFailure(payload) if int(result.get("returncode") or 0) != 0 else payload

    def resources_read(self, params: Any) -> dict:
        if not isinstance(params, dict):
            raise ToolError("resources/read params must be an object")
        uri = params.get("uri")
        if not isinstance(uri, str) or not uri:
            raise ToolError("uri is required")
        mapping = {
            "gai://project.godot": (self.project / "project.godot", "text/plain"),
            "gai://docs/testing": (self.root / "docs/gai/testing.md", "text/markdown"),
            "gai://docs/agent-bridge": (
                self.root / "docs/gai/features/agent-bridge.md",
                "text/markdown",
            ),
            "gai://logs/check": (self.runtime / "logs/check.log", "text/plain"),
            "gai://logs/test": (self.runtime / "logs/test.log", "text/plain"),
        }
        entry = mapping.get(uri)
        if entry is None:
            raise ResourceNotFound(f"resource not found: {uri}")
        path, mime_type = entry
        if not path.is_file():
            raise ResourceNotFound(f"resource is not available: {uri}")
        if path.stat().st_size > MAX_READ_BYTES:
            raise ResourceNotFound(f"resource is larger than {MAX_READ_BYTES} bytes: {uri}")
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": mime_type,
                    "text": path.read_text(encoding="utf-8", errors="replace"),
                }
            ]
        }

    def dispatch(self, method: str, params: Any) -> Any:
        if method == "initialize":
            return self.initialize(params)
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": self.tool_specs()}
        if method == "tools/call":
            return self.tools_call(params)
        if method == "resources/list":
            return {"resources": self.resource_specs()}
        if method == "resources/read":
            return self.resources_read(params)
        if method in ("notifications/initialized", "notifications/cancelled"):
            return None
        if method == "logging/setLevel":
            return {}
        raise MethodNotFound(f"method not found: {method}")

    def handle_one(self, message: Any) -> dict | None:
        if not isinstance(message, dict):
            return _error(None, -32600, "invalid request")
        method = message.get("method")
        if message.get("jsonrpc") != "2.0" or not isinstance(method, str):
            return _error(message.get("id"), -32600, "invalid request")
        notification = "id" not in message
        request_id = message.get("id")
        params = message.get("params", {})
        if method == "exit":
            self.stopped = True
            return None
        try:
            result = self.dispatch(method, params)
        except MethodNotFound as exc:
            return None if notification else _error(request_id, -32601, str(exc))
        except ToolError as exc:
            if method == "tools/call":
                result = _result_error(str(exc))
            else:
                return None if notification else _error(request_id, -32602, str(exc))
        except ResourceNotFound as exc:
            return None if notification else _error(request_id, -32002, str(exc))
        except Exception as exc:
            log(traceback.format_exc())
            if method == "tools/call":
                result = _result_error(f"internal error: {exc}")
            else:
                return None if notification else _error(request_id, -32603, f"internal error: {exc}")
        if notification:
            return None
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def handle(self, message: Any) -> Any:
        if isinstance(message, list):
            responses = []
            for item in message:
                response = self.handle_one(item)
                if response is not None:
                    responses.append(response)
            return responses or None
        return self.handle_one(message)

    def _bridge(self, method: str, params: dict) -> Any:
        try:
            value = self.bridge(method, params)
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError(str(exc)) from exc
        if isinstance(value, dict) and "$gai_error" in value:
            raise ToolError(str(value["$gai_error"]))
        return value

    def _required_string(self, arguments: dict, name: str) -> str:
        value = arguments.get(name)
        if not isinstance(value, str) or not value:
            raise ToolError(f"{name} is required")
        return value


def serve(
    bridge: Callable[[str, dict], Any],
    stdin,
    stdout,
    *,
    root: Path,
    project: Path,
    runtime: Path | None = None,
    version: str = "unknown",
    runner: Callable[[list[str], float], dict] | None = None,
    command_timeout: float = 300.0,
    event_source=None,
) -> int:
    server = Server(
        bridge,
        root,
        project,
        runtime,
        version,
        runner,
        command_timeout,
        event_source,
    )
    server.stdout = stdout
    if event_source is not None:
        event_source.set_callback(server.emit_event)
    try:
        for line in stdin:
            text = line.strip()
            if not text:
                continue
            try:
                message = json.loads(text)
            except json.JSONDecodeError as exc:
                server.write(_error(None, -32700, f"parse error: {exc}"))
                continue
            response = server.handle(message)
            if response is not None:
                server.write(response)
            if server.stopped:
                break
    finally:
        if event_source is not None:
            event_source.set_callback(None)
    return 0
