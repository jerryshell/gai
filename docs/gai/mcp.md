# MCP adapter

`bin/gai mcp` serves the existing agent bridge over the Model Context Protocol
(MCP) on stdin/stdout. It is an adapter process, not engine code. It does not
open a network port.

Use it when an MCP client such as Claude Desktop or Cursor should inspect and
edit a running gai game.

## Start a bridge

The adapter talks to a running `bin/gai agent` bridge. Start one first:

```sh
bin/gai agent start
```

Or let the adapter start the game:

```sh
bin/gai mcp --start
```

Add `--display` so `gai_screenshot` works. Add `--editor` to start the editor
instead of the game. With `--start`, the game keeps running after the MCP
process exits; stop it with `bin/gai agent stop`.

## Client configuration

MCP clients launch a command. Use an absolute path:

```json
{
  "mcpServers": {
    "gai": {
      "command": "/absolute/path/to/gai/bin/gai",
      "args": ["mcp", "--start"]
    }
  }
}
```

For a game outside this clone, set `GAI_GAME` in the client environment.

## Tools

| Tool | What it does |
| --- | --- |
| `gai_status` | Returns the project paths, gai version, and bridge ping. |
| `gai_methods` | Lists every bridge method. |
| `gai_scene_tree` | Returns the live scene tree. |
| `gai_node_get` | Reads a node by path; pass `properties` to limit it. |
| `gai_node_set` | Sets one property. A value can be JSON or Godot text such as `Vector2(10, 20)`. |
| `gai_call` | Calls any bridge method with JSON params. This is the completeness path. |
| `gai_read_file` | Reads a UTF-8 file under the game project, up to 1 MiB. |
| `gai_screenshot` | Captures the game to a PNG and returns it as image content. Needs a display. |
| `gai_test` | Runs `bin/gai test --json`; optional `filter`. |
| `gai_check` | Runs `bin/gai check` and returns its output. |
| `gai_subscribe` | Subscribes to a bridge signal by `path` or `handle`; `since` replays history. |
| `gai_unsubscribe` | Removes a subscription by id. |

`gai_call` example: `{"method": "api.autoloads", "params": {}}` discovers
project autoloads; then `{"method": "object.autoload", "params": {"name":
"Global"}}` returns one. Any bridge method works, including `object.call`.

`gai_test` and `gai_check` start a separate `bin/gai` process. They do not run
inside the game. Use `--command-timeout` to raise their limit (default 300
seconds). `gai_check` runs the full gate, including the tests.

## Events

`gai_subscribe` keeps a subscription on the adapter's persistent bridge
connection. Bridge events arrive as MCP logging notifications:

```json
{"jsonrpc": "2.0", "method": "notifications/message",
 "params": {"level": "info", "logger": "gai",
            "data": {"type": "gai.event",
                     "event": {"subscription": 1, "signal": "visibility_changed",
                               "handle": "123", "path": "/root/Main/Title",
                               "args": []}}}}
```

- Pass exactly one of `path` or `handle`, and `signal`.
- Pass `since` to replay retained events. The tool result includes `replay`,
  `lost`, and `last_seq`.
- `gai_unsubscribe` takes the `subscription` id.
- The adapter advertises the MCP logging capability. A client that does not
  show logging notifications may ignore events.
- The bridge keeps the last 512 events and replays at most 128 per subscribe.
  A game restart clears the history. A disconnect loses the subscription; pass
  `since` on the next subscribe to replay.
- A freed object sends `"closed": true` in the event.

## Resources

| URI | What it is |
| --- | --- |
| `gai://project.godot` | The game project settings. |
| `gai://docs/testing` | `docs/gai/testing.md`. |
| `gai://docs/agent-bridge` | `docs/gai/features/agent-bridge.md`. |
| `gai://logs/check` | The last check log. |
| `gai://logs/test` | The last test log. |

Resources are read-only.

## Protocol

- Line-delimited JSON-RPC 2.0 on stdin/stdout.
- MCP `2025-06-18`. The server accepts another supported version from the
  client.
- Tools, resources, batch requests, logging notifications, and JSON-RPC errors.
- stdout carries protocol messages only. Diagnostics go to stderr.
- The process exits on EOF or the `exit` notification.

## Security

- Local only. The adapter connects to `127.0.0.1` with the token from
  `.gai/agent.json`, which mode 600 protects.
- The bridge grants full local access, including `OS.execute` through
  `gai_call`/`object.call`. Treat the MCP client as trusted.
- `gai_read_file` is read-only and stays under the game project. It rejects a
  path outside the project, the bridge token file, and a file larger than 1 MiB.
- The only file the adapter writes is a temporary screenshot under
  `.gai/screenshots`; it deletes the file after reading it.
- The bridge supports up to 8 clients. The adapter keeps one persistent bridge
  connection and serializes tool calls on it.

## Limits

- Event history is in memory in the game process. A game restart clears it. A
  disconnect loses the subscription; pass `since` on the next subscribe.
- The adapter does not resubscribe automatically after a bridge restart.
- MCP cancellation is ignored. The bridge has no cancel request.
- `gai_test` and `gai_check` run separate processes. MCP cancellation does not
  stop them.
- A bridge request runs on the main thread and blocks the other clients. Keep
  calls short; `--timeout` only controls the adapter's socket.
- Screenshots need a game started with a display.
- `gai_check` can take longer than an MCP client's own timeout. Raise
  `--command-timeout` and the client timeout together.
- The log resources are capped at 1 MiB. There is no pagination.
- This is not the in-engine MCP server that Blazium's JustAMCP provides. It
  keeps gai's CLI-first bridge and adds the protocol at the edge. The design
  reference is `docs/gai/decisions/0002-cli-first.md`.
- If gai later needs durable replay or many MCP clients, add them to the bridge
  and keep this adapter thin.

## Test

```sh
python3 tests/test_mcp.py
```

The tests use a fake bridge and need no engine.
