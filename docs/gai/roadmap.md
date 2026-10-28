# Roadmap

Status: 2026-10-28. Base: Godot 4.7.2. This is a living plan, not a promise.

North star: an agent can take a game from an idea to a tested build with
engine-native tools, without a human GUI, while gai keeps merging Godot
releases.

## Done

- Godot 4.7.2 base, feature ownership, `upstream check --strict`.
- Agent bridge: reflection, handles, runtime and editor modes, screenshots.
- Up to 8 persistent bridge clients, per-client queues, signal subscriptions.
- `bin/gai` CLI: bootstrap, doctor, check, test, run, editor, export, agent,
  mcp, steam, upstream.
- Game test harness in `game/tests`: assertions, lifecycle, async waits,
  signal watching, input injection, doubles/spies/stubs, JSON results, exit
  codes, `check` integration.
- MCP stdio adapter: tools, resources, `gai_test`, `gai_check`.
- `bin/gai agent watch` for signal events.
- `bin/gai build` with source freshness, `bootstrap` rebuild, and an engine CI
  job with an SCons cache.
- JSON-RPC batch requests with a 10-second batch budget.
- MCP event forwarding over a persistent bridge connection, with MCP logging
  notifications.
- Docs: `testing.md`, `mcp.md`, feature docs, AGENTS, skill.

## P0: close the agent protocol

The bridge has multiple clients and events. The protocol still has gaps.

- A per-request deadline or a task id for long operations. Today one request
  blocks all clients on the main thread.
- Event sequence numbers and an optional replay buffer (`since`). A reconnect
  currently loses subscriptions and events.
- Add tests for deadlines and replay; batch and MCP notification tests exist.

Done when: a slow call does not block an unrelated client. MCP event delivery
is done.

## P0: test maturity

The game-level harness proves behavior, but its limits are now visible.

- Per-test timeout and isolation for a hung test.
- `double_scene` and inherited-method doubles; more stub signatures.
- JUnit or a stable JSON report for CI.
- Decide the Autowork question: port its engine-level core only if native
  `ClassDB` assertions, input recording, or the E2E server are needed.
- Keep the harness game-level until that need is proven.

Done when: a hung test fails in bounded time, CI publishes a test report, and a
scene can be doubled.

## P1: upstream 4.8

- Merge the 4.8 tag into a branch, run `upstream check --strict`, build, and
  run the bridge, game, and MCP tests.
- Resolve feature conflicts by owner; do not widen unclaimed paths.
- Keep a 4.7.2 maintenance branch if a game must stay on it.

Done when: 4.8 builds, the full test set is green, and every conflict has an
owner.

## P1: multi-agent and multi-human

Pi Pocket is shared; the bridge is still a trusted single-user interface.

- Bridge sessions with names and roles: read-only, write, admin.
- A capability policy for mutating methods; audit log for writes and
  `OS.execute`.
- Presence and scene locks for concurrent agents.
- Multiuser editor only if humans co-edit a scene. Take Blazium's lock,
  permission, CRDT, and file-sync design, not its 14k-line module blindly.
- Worktree guidance for parallel agents.

Done when: a read-only client cannot mutate, and two agents can work on one
project without silent overwrites.

## P2: production features, on demand

- Add only what a game needs: Tiled importer, SQLite, HTTP server, CSV/INI,
  GOAP, console export.
- Web export and a custom gai web template when the bridge or Steam must run in
  the browser.
- Prebuilt engine downloads and a faster first run.

Done when: each added module has an owner, docs, and tests.

## P3: ecosystem

- MCP client presets for Claude Desktop and Cursor.
- A tutorial game that starts with tests and an MCP demo.
- Public docs and a skill pack.
- A changelog that agents can read.

Done when: a new user can go from clone to a tested game without reading the
engine source.

## Blazium mapping

| Blazium | gai decision |
| --- | --- |
| Autowork | Borrowed the test shape. Native port deferred until ClassDB/E2E needs appear. |
| JustAMCP | Borrowed multi-client, event, queue, and protocol ideas. Keep a thin adapter, not a 79k-line in-engine server. |
| Multiuser editor | Conditional. Take locks, permissions, CRDT, file sync if humans co-edit. |
| 60+ game modules | On demand. Breadth is not gai's product. |
| Hub, CLI, skills | Not needed; `bin/gai`, AGENTS, and skills cover this. |

## Guardrails

- No in-engine MCP server. Keep the bridge as the API and MCP at the edge.
- No 60-module breadth by default.
- No broad UI rebrand; it moves upstream files into the merge surface.
- No remote MCP listener until authentication and a sandbox exist.
- No multiuser editor before roles and locks.
- Every engine change has a feature owner; `upstream check --strict` stays the
  CI gate.

## Metrics

- Time from edit to a green `bin/gai check`.
- Share of engine features with a build and a test.
- MCP tool success rate and latency.
- Upstream merge conflicts per release.
- Agent tasks completed without a human GUI.

## Next three tasks

1. A per-request deadline or task id; a long single request still blocks all clients.
2. Event replay and history for reconnects.
3. Test timeout, JUnit output, and `double_scene`.
