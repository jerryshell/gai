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
| `object` | `get`, `set`, `call`, `properties`, `methods`, `signals`, `singleton`, `autoload`, `free` | Any live object, any property, any method, any signal list. |
| `api` | `methods`, `singletons`, `autoloads` | The bridge surface, the engine singleton registry, and project autoloads. |

`object.singleton` reaches `Engine`, `OS`, `ProjectSettings`, `Input`,
`PhysicsServer2D`, `PhysicsServer3D`, `RenderingServer`, `AudioServer`,
`NavigationServer2D`, `NavigationServer3D`, `EditorInterface`, and every other
registered singleton. `api.singletons` returns a handle for each.

Project autoloads are not engine singletons. `api.autoloads` lists them with
`name`, `path`, `singleton`, and a `handle` when the node exists.
`object.autoload` with `{"name": "Global"}` returns the autoload node. The
`singleton` field is true when `project.godot` marks it with `*`; it does not
mean the engine singleton registry. In editor mode an autoload may not be
instantiated, so it can have no handle.

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
| `event` | `subscribe`, `unsubscribe`, `list` | Signal subscriptions. A subscription needs a persistent connection. |
| `client` | `list` | Connected clients, their subscriptions, and their output backlog. |

Errors are JSON-RPC errors. A normal result dictionary that contains an `error`
key is preserved and returned as data.

In editor mode, `scene.tree` returns the edited scene when one is open. Its paths
are editor-internal. Prefer handles from `EditorInterface.get_edited_scene_root`.
`run.*`, `scene.change`, and `input.*` are refused without `force: true` so an
agent cannot quit or pause the editor by accident.

## Events

A client can subscribe to a signal and keep the connection open. Events are
JSON-RPC notifications without an `id`:

```json
{"jsonrpc": "2.0", "id": 1, "method": "event.subscribe",
 "params": {"path": "/root/Main/Title", "signal": "visibility_changed"},
 "token": "<token>"}
```

The response carries a subscription id and the last sequence number. The
server then sends:

```json
{"jsonrpc": "2.0", "method": "event",
 "params": {"subscription": 1, "seq": 7, "signal": "visibility_changed",
            "handle": "123", "path": "/root/Main/Title", "args": []}}
```

- Pass `handle` or `path` to select the object, and `signal` to name the signal.
- `event.unsubscribe` with `{"subscription": 1}` removes it.
- `event.list` returns this client's subscriptions.
- `client.list` returns connected clients, subscription counts, and output backlog.
- A freed object sends `"closed": true` and removes the subscription.
- Signal arguments use the same JSON conversion as results. A value that is not
  JSON becomes Godot text, such as `Vector2(0, 0)`.
- A subscription needs a persistent connection. `bin/gai agent call` opens one
  connection per call; use `bin/gai agent watch` or a raw socket for events.
- Signals must be emitted on the main thread. A signal emitted from a worker
  thread can race with the bridge queues.
- Subscribers for the same object and signal share one engine connection. One
  emission records one event and reaches every subscriber with the same `seq`.
- The server keeps the last 512 events. An event is recorded while at least one
  subscription exists; a replay can still return events after the last
  subscriber leaves.

## Event replay

Add `since` to `event.subscribe` to replay recorded events:

```json
{"jsonrpc": "2.0", "id": 2, "method": "event.subscribe",
 "params": {"path": "/root/Main/Title", "signal": "visibility_changed",
            "since": 5},
 "token": "<token>"}
```

The response then also has:

- `replay`: events with `seq` greater than `since`, oldest first, at most 128.
- `lost`: true when `since` is older than the retained history or the replay
  was truncated.
- `last_seq`: the latest event sequence before the subscription.

A client that knows `last_seq` passes it as `since` on reconnect. A `since` of 0
asks for all retained events for that object and signal. Events are not deduped
against `since`; the client should drop an event whose `seq` it already has.

```sh
bin/gai agent watch --path /root/Main/Title --signal visibility_changed
bin/gai agent watch --handle 123 --signal ready --count 1
```

## Batch requests

A line can be a JSON-RPC array. Every element carries its own token and its own
`id`. The reply is one JSON array of responses; notifications are omitted.

- At most 64 elements. A larger batch gets one invalid-request error.
- The server spends at most 10 seconds on one batch. Remaining requests with an
  `id` get `-32000 Batch deadline exceeded` without running.
- An empty array is invalid.
- A single request still runs synchronously on the main thread. The batch
  deadline cannot interrupt the request that is already running.

## CLI

```sh
bin/gai agent start
bin/gai agent methods
bin/gai agent call api.autoloads '{}'
bin/gai agent call object.autoload '{"name":"Global"}'
bin/gai agent call classdb.classes '{}'
bin/gai agent call classdb.class '{"name":"Node2D"}'
bin/gai agent call object.singleton '{"name":"PhysicsServer3D"}'
bin/gai agent call object.methods '{"handle":"<handle>"}'
bin/gai agent call object.call '{"handle":"<handle>","method":"get_class","args":[]}'
bin/gai agent watch --path /root/Main/Title --signal visibility_changed
bin/gai agent log
bin/gai agent stop
```

`bin/gai agent log` tails the game output. `bin/gai agent call` is the generic
path: any bridge method can be called without a new CLI command. `tree`, `get`,
and `set` remain path-based sugar. `bin/gai agent watch` keeps one connection
open, prints each event notification as one JSON line on stdout, and writes its
status to stderr. `--count N` stops after N events.

## Security

- A random token per session. It is stored in `.gai/agent.json` with mode 600.
- Bind 127.0.0.1 only.
- Up to 8 clients. Each request must carry the token. A request runs on the main
  thread, so it blocks the other clients while it runs; keep calls short.
- One client can hold up to 64 subscriptions. A client without subscriptions is
  dropped after 10 minutes idle. A client whose output backlog passes 4 MiB is
  dropped.
- `agent stop` checks the process start time and engine path before signaling.
- Full access is intentional. The token holder can call `OS.execute`, write
  arbitrary paths through `resource.save` or `render.screenshot`, and change the
  engine source. gai is a trusted local agent interface, not a sandbox.

## Tests

```sh
python3 tests/test_agent.py
```

Nine tests: scene get/set and auth, capability surface, autoloads, editor mode,
concurrent start, foreign PID safety, multi-client event delivery, event replay,
and batch requests. They need a source build. The `engine` CI job builds the
engine and runs them. A local run needs a binary built from the current HEAD.

## Not yet

- A per-request deadline or task id. A long single request blocks all clients
  until it returns; the batch deadline only bounds the next batch item. Read
  `docs/gai/decisions/0004-synchronous-requests.md`.
- Durable event history. The last 512 events live in memory; a restart clears
  them.
- Export helpers. Export internals are reachable through editor objects when
  they are exposed as singletons or objects.
- Screenshots in headless CI. Use `--display` with a virtual display.
- A prebuilt gai engine. The first build is from source.

## Upstream risk

Medium. The module depends on `ClassDB`, `Object`, the singleton registry, the
`jsonrpc` module, and the TCP/JSON APIs. Upstream changes to those surfaces can
break it.
