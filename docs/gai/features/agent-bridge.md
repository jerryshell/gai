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
| `script` | `classes`, `class` | Every GDScript `class_name`, its properties, methods, signals, constants, and doc. |
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
`ClassDB`; `script.*` reaches them without a read of the source file.

## Script classes

`classdb.*` reflects the engine. `script.*` reflects the game's own scripts, so
an agent does not have to read and parse a `.gd` file to learn its surface.

```sh
bin/gai agent call script.classes '{}'
bin/gai agent call script.class '{"name":"Player"}'
bin/gai agent call script.class '{"path":"res://scripts/player.gd"}'
```

`script.classes` returns `classes`, `count`, and `cached`. Each entry has
`class`, `path`, `base`, `language`, and `source`. `source` is `import cache`
for a class the engine registered, and `res:// scan` for a class found by
reading the project. The engine writes its global class cache in the editor
only, so a game run starts without one: the scan is what makes a fresh project
answer.

`script.class` takes `name` or `path` and returns:

- `class`, `name`, `path`, `base`, `language`, `tool`, `cached`;
- `properties`, with `name`, `type`, `type_name`, `hint`, `hint_string`, `usage`,
  and `exported`;
- `methods` and `signals`, with arguments, return type, and defaults;
- `constants`, as values when they are JSON, skipped when they are objects;
- `doc`, when the build carries the parsed class doc: brief, description, and
  per-member text.

The bridge keeps a loaded script per path, keyed by file modification time. A
second call reports `"cached": true`. `script.classes` with `{"refresh":true}`
drops both the scan and the loaded scripts. A class name that no script declares
is an error, not null.

A reload parses the file again instead of asking `ResourceCache`. Both reuse and
replace route to `GDScriptCache` and keep returning the script that was loaded
the first time, so an edited script would report its old properties and old doc
forever. The cost is one parse per script per change, not one per call.

The scan reads up to 2000 `.gd` files under `res://` and skips folders whose
name starts with `.`.

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
| `client` | `list` | Connected clients, their role, subscriptions, and output backlog. |
| `lock` | `acquire`, `release`, `list` | A node subtree is held by a holder name for a TTL. |

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

## Crash record

A fatal signal in the game process ends the engine. Before it dies, the bridge
writes one file that names the call it was running:

```json
{"schema": 1, "pid": 4242, "method": "object.call",
 "target": "handle=335544339 call=spin", "started_ms": 48123,
 "signal": "SIGSEGV", "signal_num": 11}
```

- The path is `.gai/logs/bridge-crash.json`, set through `GAI_CRASH_RECORD` by
  `bin/gai agent start`. Without that variable the bridge uses the engine user
  data directory.
- The record is formatted before the call and written by the handler with one
  `write`, so the handler allocates nothing and takes no lock.
- A clean shutdown deletes the record. A record therefore always describes a
  crash that has no response.
- A read-only bridge client sees the reason instead of a dead socket:
  `bin/gai agent call` and `bin/gai agent status` print the method, the target,
  and the signal.
- The signal is handed back to the default handler, so the core dump and the
  engine's own crash path still run. The bridge does not resume the call.
- Linux and macOS only. On Windows there is no record.

## Roles

A role comes from the token. `bin/gai agent start` mints one token per role and
writes them to `.gai/agent.json` beside the admin token that older clients read:

```json
{"token": "<admin>", "tokens": {"admin": "…", "write": "…", "read-only": "…"}}
```

`bin/gai agent call --role read-only …`, `bin/gai agent watch` (read-only by
default), and `bin/gai mcp --role read-only` send the token for that role. A
token that the bridge does not know is `-32001 Unauthorized`, the same answer as
before, so a role cannot be claimed by asking for it.

`--role` on `agent start` is a ceiling for the whole process: every token is
capped at it, and a bridge started read-only cannot be raised by any token.
`ping` reports `role` (the ceiling), `caller` (the role this token carries),
`access` (the effective access), and `roles` (what the process was given).

| Role | May call |
| --- | --- |
| `read-only` | The read methods: `ping`, `api.*`, `classdb.*`, `script.*`, `object.get/properties/methods/signals/singleton/autoload`, `scene.tree/current`, `node.get`, `resource.load`, `project.get`, `run.status`, `event.*`, `client.list`. |
| `write` | Every read method plus the mutating ones: `object.set/call/free`, `node.set/create/delete/reparent/add_child`, `resource.save`, `project.set/save`, `run.pause/resume/step/time_scale`, `input.*`, `render.screenshot`. |
| `admin` | Everything, including `scene.change`, `run.quit`, and any method the table does not name. |

A request can lower its own ceiling with a `ceiling` field, which a client uses
to promise it will not mutate even while it holds an admin token. Raising is not
a request, only a lowering. `--ceiling` on `agent call` sets it.

One table in `modules/gai_agent/gai_agent_server.cpp` decides, and a method that
is not in it needs an admin. A new method is therefore closed until someone
classifies it. A refused call returns JSON-RPC error `-32003` and names the role
the method needs and the role the token carries.

`object.call` is one entry, so a write role can reach any method through it,
including `OS.execute`. The role bounds the bridge surface, not the engine. A
read-only bridge is the only role that cannot mutate at all.

## Locks and presence

Two agents on one scene overwrote each other in silence. A lock is a claim on a
node and its whole subtree, held by a name the caller chooses:

```sh
bin/gai agent call lock.acquire '{"path":"/root/Main","holder":"agent-a","note":"level pass"}' --holder agent-a
bin/gai agent call lock.list '{}'
bin/gai agent call lock.release '{"lock":1,"holder":"agent-a"}' --holder agent-a
```

- A path-addressed write (`node.set`, `node.create`, `node.delete`,
  `node.reparent`, `node.add_child`) and a write on a node handle (`object.set`,
  `object.call`, `object.free`) inside a held subtree returns `-32004` and names
  the holder.
- A request carries its holder as `"holder"`. A request with no holder is a
  guest and is blocked by every lock. `--holder` on `agent call` sets it.
- A lock lives until it is released or its TTL expires, which defaults to 120
  seconds and takes `ttl_ms` on acquire. A lock does not die with a connection,
  because `agent call` opens one connection per call.
- Acquiring a path twice with the same holder returns the same lock with
  `reused: true`, so a stateless client can acquire before every write.
- `object.call` cannot be inspected, so any lock over the target node blocks it,
  including a call that would only read.
- `lock.list` shows the holder, the path, the note, and the time left.
  `client.list` shows the connected clients with their role and idle time, and
  `ping` counts the locks in the process.

## Audit log

Every request whose access is `write` or `admin` appends one line to
`.gai/logs/audit.jsonl` before it runs, allowed or refused:

```json
{"ts":"2026-11-03T16:03:11","pid":2111235,"client":4,"role":"read-only",
 "ceiling":"admin","access":"write","method":"node.set","target":"path=/root/Main",
 "allowed":false}
```

A call through `object.call` also carries `effect`, the class and the method the
client actually reached, so a passthrough is named:

```json
{"role":"admin","access":"write","method":"object.call",
 "target":"handle=36028797018963969 call=execute","effect":"OS.execute","allowed":true}
```

- `target` is the handle, path, and called method the request named.
- Reads are not logged, so the file holds only the calls that change something
  or try to.
- The path comes from `GAI_AUDIT_LOG`; without it the bridge uses the engine
  user data directory.
- The line is written and flushed per request, so a crash keeps the trail.

## Security

- A random token per session. It is stored in `.gai/agent.json` with mode 600.
- A role bounds what the token can do. The three tokens live in one file with
  mode 600, so keeping a reviewer to reads means giving them the read-only token
  and not the file.
- `--role` on `agent start` caps the whole process, which is the belt to the
  token's braces.
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

Eighteen tests: scene get/set and auth, capability surface, autoloads, editor mode,
concurrent start, foreign PID safety, multi-client event delivery, event replay,
and batch requests. `test_read_only_role_refuses_a_write`,
`test_each_token_carries_its_own_role`, `test_admin_write_is_audited_and_a_read_is_not`,
and `test_the_audit_line_names_a_passthrough_call` cover the role table and the
audit log. `test_a_request_can_lower_its_own_ceiling`,
`test_a_lock_blocks_another_holder`, and `test_a_lock_covers_a_write_through_a_handle`
cover the ceiling and the locks. `test_script_reflection` covers `script.classes` and
`script.class`. `test_crash_record_names_the_call` sends `SIGSEGV` during a
blocking call and reads the record back. They need a source build. The `engine`
CI job builds the engine and runs them. A local run needs a binary built from
the current HEAD.

## Not yet

- A per-request deadline or task id. A long single request blocks all clients
  until it returns; the batch deadline only bounds the next batch item. Read
  `docs/gai/decisions/0004-synchronous-requests.md`.
- A protected call. A fatal signal still ends the process; the record names the
  call but cannot contain the fault. Linux has no structured exception handler,
  and a `longjmp` out of a signal handler leaves engine locks held.
- A crash record on Windows, which would need an unhandled-exception filter.
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
