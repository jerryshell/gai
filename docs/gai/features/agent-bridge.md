# Engine agent bridge

Status: active, first slice
Risk: medium
Manifest: `.gai/features/agent-bridge.json`

## What works

`bin/gai agent start` starts the game headless with `GAI_AGENT_PORT` and
`GAI_AGENT_TOKEN`. The module `modules/gai_agent/` listens on 127.0.0.1 and
speaks JSON-RPC 2.0 over newline-delimited JSON. The CLI can read the scene
tree, read node properties, and set a property.

- The token is random per session. The CLI stores the pid, port, token, engine,
  and process start time in `.gai/agent.json` with mode 600. Git ignores the
  file. `agent start` and `agent stop` take a lock.
- The server binds 127.0.0.1 only. It serves one client at a time. A request
  must finish within 10 seconds. A new idle client replaces an idle connection;
  extra connections during a request are dropped. The server closes after one
  response. A notification gets no response.
- The server uses the engine `jsonrpc` module for dispatch and error responses.
  gai buffers newline-delimited frames and writes responses with
  `put_partial_data`, so a slow reader does not block the game frame.
- A node path or property error is a JSON-RPC `-32602` error. The CLI exits 1.
- `bin/gai agent start` refuses the downloaded engine. The bridge is only in a
  source build with `modules/gai_agent/`.
- `agent stop` verifies the process start time and the engine path before it
  sends a signal. A reused pid is not killed.

## Commands

```sh
bin/gai agent start
bin/gai agent status
bin/gai agent tree
bin/gai agent get /root/Main --property visible
bin/gai agent set /root/Main visible false
bin/gai agent stop
```

## Methods

| Method | State | Result |
| --- | --- | --- |
| `ping` | implemented | Engine name and process id. |
| `scene.tree` | implemented | Recursive node tree with names, types, paths, and scripts. |
| `node.get` | implemented | Node info plus the requested properties. |
| `node.set` | implemented | Set one property. Returns the new value. |
| `node.call` | planned | Call a method with JSON arguments. |
| `run.start` | planned | Start the main scene or a named scene. |
| `run.stop` | planned | Stop the running scene. |
| `run.status` | planned | Running state, frame count, and current scene. |
| `input.action` | planned | Press or release an input action for N frames. |
| `input.key` | planned | Send a key event. |
| `input.mouse` | planned | Move or click at viewport coordinates. |
| `screenshot` | planned | Capture the viewport to a PNG path. |
| `log.tail` | planned | Return recent engine and game output. |
| `test.run` | planned | Run a scene for N frames and collect errors. |

## Tests

Run the tests with:

```sh
python3 tests/test_agent.py
```

The tests copy `game/` to a temporary directory, start the bridge, read the
tree, change `visible`, and read it back. They also check the auth and parse
errors, the state file mode, a second start, concurrent starts, and that stop
does not kill a foreign pid. They need a source build with the module. CI does
not run them without an engine build.

## Build

The source build includes the module. The downloaded official engine does not.
`bin/gai agent start` refuses a downloaded engine with a clear message.

The module depends on the `jsonrpc` module, which is on by default. If you
disable `jsonrpc`, the gai module does not build.

## Not yet

- Run control, input injection, screenshots, log tail, and test scenes.
- Editor mode. The current server runs in the game process.
- Batch requests, more than one client, and binding the port inside the engine.
- A prebuilt gai engine for users who do not build. The default `bootstrap`
  still downloads the official Godot binary.

## Upstream risk

Medium. The feature is a new module with no main or editor hook. It depends on
the `jsonrpc` module and the TCP and JSON APIs, which upstream can change.
