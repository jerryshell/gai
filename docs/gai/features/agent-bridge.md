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
  `{"$handle": "<id>"}`. Other engine values use Godot text, such as
  `"Vector2(10, 20)"`.
- Loaded resources and RefCounted objects stay alive in the bridge until
  `object.free` or shutdown. Tree nodes live in the scene tree.

## Reflection

| Namespace | Methods | What it reaches |
| --- | --- | --- |
| `classdb` | `classes`, `class`, `instantiate` | Every class, its properties, methods, signals, constants, and enums. |
| `object` | `get`, `set`, `call`, `properties`, `methods`, `signals`, `singleton`, `free` | Any live object, any property, any method, any signal list. |
| `api` | `methods`, `singletons` | The bridge surface and the engine singleton registry. |

`object.singleton` reaches `Engine`, `OS`, `ProjectSettings`, `Input`,
`PhysicsServer2D`, `PhysicsServer3D`, `RenderingServer`, `AudioServer`,
`NavigationServer2D`, `NavigationServer3D`, `EditorInterface`, and every other
registered singleton. This is the completeness path: if `ClassDB` knows it,
the agent can discover and call it.

## Subsystems

| Namespace | Methods | Notes |
| --- | --- | --- |
| `scene` | `tree`, `current`, `change` | Tree includes handles. |
| `node` | `get`, `set`, `create`, `delete`, `reparent`, `add_child` | Path based. |
| `resource` | `load`, `save` | Engine resources, not shell file access. |
| `project` | `get`, `set`, `save` | Project settings. |
| `run` | `status`, `pause`, `resume`, `step`, `time_scale`, `quit` | `step` restores the previous pause state. |
| `input` | `action`, `key`, `mouse` | Injects input events. |
| `render` | `screenshot` | Needs a display; headless returns an error. |

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
- Full access is intentional. The engine source is fully editable, so the agent
  can add bridge methods when a capability needs one.

## Tests

```sh
python3 tests/test_agent.py
```

Five tests: scene get/set and auth, capability surface, editor mode, concurrent
start, and foreign PID safety. They need a source build. CI does not build the
engine yet, so it skips them.

## Not yet

- Event subscriptions and streaming. The agent polls.
- Multiple clients and batch requests.
- Export helpers. Export internals are reachable through editor objects when
  they are exposed as singletons or objects.
- Screenshots in headless CI. Use `--display` with a virtual display.
- A prebuilt gai engine. The first build is from source.

## Upstream risk

Medium. The module depends on `ClassDB`, `Object`, the singleton registry, the
`jsonrpc` module, and the TCP/JSON APIs. Upstream changes to those surfaces can
break it.
