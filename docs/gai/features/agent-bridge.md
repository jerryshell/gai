# Engine agent bridge

Status: active
Risk: medium
Manifest: `.gai/features/agent-bridge.json`

## What it is

A JSON-RPC 2.0 server inside the gai engine. It exposes the engine's own
reflection and an object handle model, so an agent can reach every class,
property, method, signal, and singleton. It does not wrap each feature one at a
time. Subsystem methods cover the common operations, and `object.call` reaches
everything else.

## Modes

- Runtime: `bin/gai agent start` starts the game headless. Add `--display` for
  rendering and screenshots.
- Editor: `bin/gai agent start --editor` starts the editor. Its singletons,
  including `EditorInterface`, are reachable. `scene.tree` shows the editor tree;
  use `EditorInterface.get_edited_scene_root` for the edited scene.

## Handles

- A handle is the engine `ObjectID` as a decimal string.
- `scene.tree`, `object.singleton`, `classdb.instantiate`, and `resource.load`
  return handles.
- Pass a handle as a string in `handle`. Pass an object argument as
  `{"$handle": "<id>"}`. An unknown handle is an error, not null.
- A string stays a string when the target property or argument is a string.
  For a non-string target the bridge parses Godot text, such as
  `"Vector2(10, 20)"`. Use `{"$var": "..."}` inside a generic dictionary or a
  project setting.
- Reads return non-JSON values as `var_to_str` text, such as `Vector2(0, 0)`,
  so they can be sent back. Containers convert recursively; depth is capped at
  64.
- Loaded resources and RefCounted objects stay alive in the bridge until
  `object.free` or shutdown. `object.free` refuses engine singletons and game
  objects; it frees only handles the bridge created. Use `node.delete` for a
  tree node.

## Reflection

| Namespace | Methods | What it reaches |
| --- | --- | --- |
| `classdb` | `classes`, `class`, `instantiate` | Every class, its properties, methods, signals, constants, and enums. |
| `object` | `get`, `set`, `call`, `properties`, `methods`, `signals`, `singleton`, `free` | Any live object, any property, any method, any signal list. |
| `api` | `methods`, `singletons` | The bridge surface and the engine singleton registry. |

`object.singleton` reaches `Engine`, `OS`, `ProjectSettings`, `Input`,
`PhysicsServer2D`, `PhysicsServer3D`, `RenderingServer`, `AudioServer`,
`NavigationServer2D`, `NavigationServer3D`, `EditorInterface`, and every other
registered singleton. `api.singletons` returns a handle for each.

This is the completeness path for native classes: if `ClassDB` knows it, the
agent can discover and call it. GDScript `class_name` classes are not in
`ClassDB`; reach them through node or object handles.

## Subsystems

| Namespace | Methods | Notes |
| --- | --- | --- |
| `scene` | `tree`, `current`, `change` | Tree includes handles. |
| `node` | `get`, `set`, `create`, `delete`, `reparent`, `add_child` | Path based. |
| `resource` | `load`, `save` | Engine resources, not shell file access. |
| `project` | `get`, `set`, `save` | Project settings. |
| `run` | `status`, `pause`, `resume`, `step`, `time_scale`, `quit` | `step` restores the previous pause state. Guarded in editor mode. |
| `input` | `action`, `key`, `mouse` | Injects input events. Guarded in editor mode. |
| `render` | `screenshot` | Needs a display; headless returns an error. |

Errors are JSON-RPC errors. A normal result dictionary that contains an `error`
key is preserved and returned as data.

In editor mode, `scene.tree` returns the edited scene when one is open. Its paths
are editor-internal. Prefer handles from `EditorInterface.get_edited_scene_root`.
`run.*`, `scene.change`, and `input.*` are refused without `force: true` so an
agent cannot quit or pause the editor by accident.

## CLI

```sh
bin/gai agent start
bin/gai agent methods
bin/gai agent call classdb.classes '{}'
bin/gai agent call classdb.class '{"name":"Node2D"}'
bin/gai agent call object.singleton '{"name":"PhysicsServer3D"}'
bin/gai agent call object.methods '{"handle":"<handle>"}'
bin/gai agent call object.call '{"handle":"<handle>","method":"get_class","args":[]}'
bin/gai agent log
bin/gai agent stop
```

`bin/gai agent log` tails the game output. `bin/gai agent call` is the generic
path: any bridge method can be called without a new CLI command. `tree`, `get`,
and `set` remain path-based sugar.

## Security

- A random token per session. It is stored in `.gai/agent.json` with mode 600.
- Bind 127.0.0.1 only.
- One client at a time. A request must finish within 10 seconds. An idle client
  is replaced; an extra connection during a request is dropped.
- `agent stop` checks the process start time and engine path before signalling.
- Full access is intentional. The token holder can call `OS.execute`, write
  arbitrary paths through `resource.save` or `render.screenshot`, and change the
  engine source. gai is a trusted local agent interface, not a sandbox.

## Tests

```sh
python3 tests/test_agent.py
```

Five tests: scene get/set and auth, capability surface, editor mode, concurrent
start, and foreign PID safety. They need a source build. The `engine` CI job
builds the engine and runs them. A local run needs a binary built from the
current HEAD.

## Not yet

- Event subscriptions and streaming. The agent polls. Signals can be listed
  and emitted, but not connected or awaited.
- Multiple clients and batch requests.
- Export helpers. Export internals are reachable through editor objects when
  they are exposed as singletons or objects.
- Screenshots in headless CI. Use `--display` with a virtual display.
- A prebuilt gai engine. The first build is from source.

## Upstream risk

Medium. The module depends on `ClassDB`, `Object`, the singleton registry, the
`jsonrpc` module, and the TCP/JSON APIs. Upstream changes to those surfaces can
break it.
