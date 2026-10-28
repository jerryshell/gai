# 0004 Keep bridge requests synchronous

Date: 2026-10-28
Status: accepted

## Context

The bridge runs inside the game process. A request calls engine methods on the
main thread. Godot's scene, rendering, input, and resource APIs are not
thread-safe, and the bridge exposes `object.call`, so it can reach any method.

The roadmap asked for a per-request deadline or a task id. A true deadline must
stop work that already started. That needs one of:

- preemptive cancellation of an arbitrary engine call;
- a worker thread that calls engine APIs;
- a separate process that owns the same live scene.

None is safe today. A watchdog can send an error to the client while the method
keeps running, but the side effects still happen and the main thread still
blocks. That is a lie in the protocol.

## Decision

Bridge requests stay synchronous.

- A batch has a 10-second budget between items. It cannot interrupt the item
  that is running.
- Clients use their own socket timeout. `bin/gai agent call` and the MCP
  adapter have `--timeout`.
- Long commands that do not touch the live scene run as separate `bin/gai`
  processes: `gai_test` and `gai_check` in the MCP adapter.
- A future `task.start` is allowed only for a whitelisted operation that can be
  split into main-thread steps with a cancellation check between steps. It must
  not accept `object.call` or any arbitrary engine method.
- No `deadline_ms` field is added to requests. A field that cannot stop the
  method would mislead agents.

## Consequences

- One slow bridge call blocks the other clients until it returns. The bridge
  documentation says to keep calls short.
- Agents that need long work should use a separate CLI process, a file, or a
  signal subscription instead of one long bridge call.
- A slow call is visible in client timeouts and in `client.list` output backlog,
  not in a bridge error.
- The batch budget still protects a client from an unbounded batch of small
  calls.

## Revisit

Revisit when a real game needs a long bridge operation that cannot run as a
separate process. Then design `task.start`, `task.status`, and `task.cancel` for
that operation only, with a cancellation check between main-thread steps, and
document that arbitrary `object.call` is not cancellable.
