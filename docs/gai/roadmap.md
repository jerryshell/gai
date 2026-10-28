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
- JUnit reports, `double_scene`, and per-file/per-test isolation with timeouts.
- `bin/gai build` with source freshness, `bootstrap` rebuild, and an engine CI
  job with an SCons cache.
- JSON-RPC batch requests with a 10-second batch budget.
- Event sequence numbers and an in-memory replay buffer.
- MCP event forwarding over a persistent bridge connection, with MCP logging
  notifications.
- Docs: `testing.md`, `mcp.md`, feature docs, AGENTS, skill.
- Scene-test discovery with JUnit, native Windows/Linux export with preflight and
  checksums, template builds, external-game `init`, and bridge autoload discovery.

## P0: close the agent protocol

Status: batch, per-client queues, event sequence numbers, replay, and MCP event
forwarding are done. One limit remains.

- A per-request deadline is not implemented. `decisions/0004` records why: the
  bridge calls non-thread-safe engine APIs on the main thread. A deadline field
  that cannot stop the call would mislead agents.
- A slow call still blocks the other clients. Clients use socket timeouts.
- The remaining acceptance test: a slow call must not block an unrelated client.
  That needs a task protocol for safe operations, not a deadline field.

## P0: test maturity

Done. The harness writes JUnit XML, doubles scripts and scenes, isolates test
files, and isolates each test method with a timeout. A hung test now fails in
bounded time without losing the rest of its file.

Remaining optional work: more stub signatures, inherited-method doubles, and
the Autowork decision if native `ClassDB` assertions or the E2E server are
needed.

## Deferred: upstream 4.8

Waiting for the 4.8 stable tag. Do not rehearse against 4.8 dev.

- The base stays `4.7.2-stable`. Keep merging nothing from 4.8 dev.
- When 4.8 stable is tagged: merge it into a branch, run
  `upstream check --strict`, build, and run the bridge, game, and MCP tests.
- Resolve feature conflicts by owner; do not widen unclaimed paths.
- Keep a 4.7.2 maintenance branch if a game must stay on it.

Done when: the stable tag exists, 4.8 builds, the full test set is green, and
every conflict has an owner.

Why not now: a dev tag is a moving target. A rehearsal against it would test
code that will change before release, and it would pull dev-only conflicts into
the base without a release to justify them.

## P1: multi-agent and multi-human (next)

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
- Upstream merge conflicts per release, measured after 4.8 stable.
- Agent tasks completed without a human GUI.

## Next three tasks

1. Multi-agent roles: read-only, write, and admin sessions, with an audit log.
2. Dogfood the new path on nova-survivors-gai: scene tests in CI, native export,
   and template rebuild after engine changes.
3. Test maturity leftovers: more stub signatures and inherited-method doubles.
