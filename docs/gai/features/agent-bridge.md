# Engine agent bridge

Status: active, first slice
Risk: medium
Manifest: `.gai/features/agent-bridge.json`

## What works

`bin/gai agent start` starts the game headless with `GAI_AGENT_PORT` and
`GAI_AGENT_TOKEN`. The module `modules/gai_agent/` listens on 127.0.0.1 and
speaks JSON-RPC 2.0 over newline-delimited JSON. The CLI can read the scene
tree, read node properties, and set a property.

- The token is random per session. The CLI stores the pid, port, and token in
  `.gai/agent.json` with mode 600. Git ignores the file.
- The server binds 127.0.0.1 only. It closes a client after one response and
  drops a client that sends nothing for 10 seconds.
- The server reuses the engine `jsonrpc` module for framing and errors.
- `bin/gai agent start` refuses the downloaded engine. The bridge is only in a
  source build with `modules/gai_agent/`.

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

`tests/test_agent.py` copies `game/` to a temporary directory, starts the
bridge, reads the tree, changes `visible`, and reads it back. It needs a source
build with the module.

## Build

The source build includes the module. The downloaded official engine does not.
`bin/gai agent start` refuses a downloaded engine with a clear message.

The module depends on the `jsonrpc` module, which is on by default. If you
disable `jsonrpc`, the gai module does not build.

## Not yet

- Run control, input injection, screenshots, log tail, and test scenes.
- Editor mode. The current server runs in the game process.
- A prebuilt gai engine for users who do not build. The default `bootstrap`
  still downloads the official Godot binary.

## Upstream risk

Medium. The feature is a new module with no main or editor hook. It depends on
the `jsonrpc` module and the TCP and JSON APIs, which upstream can change.
