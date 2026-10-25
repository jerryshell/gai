# Engine agent bridge

Status: planned
Risk: high
Manifest: `.gai/features/agent-bridge.json`

## Why

`bin/gai` can run the game and check it, but it cannot see live editor state. An
agent cannot inspect the scene tree, read a viewport, or inject input through a
process that only launches the game. The engine can expose those directly.

This is the first vertical AI-native feature. It is not a wrapper around the
editor. It runs inside the engine.

## Shape

- A new module under `modules/gai_agent/`.
- Two small hooks: start and stop the server from `main/main.cpp` and
  `editor/editor_node.cpp`. All protocol code stays in the module.
- JSON-RPC 2.0 over a localhost TCP socket, one JSON object per line.
- Editor mode and runtime mode.
- `bin/gai agent` will be the client. There is no separate daemon.

## Methods

| Method | Result |
| --- | --- |
| `scene.tree` | Nodes, types, scripts, scene paths, and selected properties. |
| `node.get` | One node's properties and children. |
| `node.set` | Set one property. |
| `node.call` | Call a method with JSON arguments, return the result. |
| `run.start` | Start the main scene or a named scene. |
| `run.stop` | Stop the running scene. |
| `run.status` | Running state, frame count, and current scene. |
| `input.action` | Press or release an input action for N frames. |
| `input.key` | Send a key event. |
| `input.mouse` | Move or click at viewport coordinates. |
| `screenshot` | Capture the viewport to a PNG path. |
| `log.tail` | Return recent engine and game output. |
| `test.run` | Run a scene headlessly for N frames, collect errors and a screenshot. |

## Security

- Bind `127.0.0.1` only. There is no remote mode.
- Write a random token to `.gai/agent.token`. The file is ignored by git.
- Every request must carry the token.
- The server will be off by default. The planned `bin/gai agent start` command
  will turn it on for a session.

## Tests

- Unit tests for the request parser and the JSON schema.
- A headless editor test that opens `game/`, reads the scene tree, changes one
  property, and reads it back.
- A runtime test that starts the game, presses an action, and asserts a node
  moved.
- A screenshot test with a fixed viewport and a hash or pixel diff.
- A test that a bad token and a non-local bind are refused.

Screenshots need a rendering context. A headless engine has none. CI uses a
virtual display or a future offscreen renderer; the design must keep that path
explicit.

## Milestones

1. `scene.tree`, `node.get`, `node.set`, and the CLI client. Tests on a sample
   scene.
2. `run.start`, `run.stop`, `input.*`, and `screenshot`. Runtime integration
   tests.
3. `test.run`, log tail, baselines, and CI with an engine build.

## Upstream risk

High. The hooks sit in `main/main.cpp` and `editor/editor_node.cpp`, both busy
upstream files. Keep the protocol in the module so the hooks stay small.

## Not done

Nothing is implemented. This file is the design.
