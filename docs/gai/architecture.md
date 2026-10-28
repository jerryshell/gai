# Architecture

gai is a deep fork of Godot 4.7.2, built around agents as first-class users. The
engine is part of the product. We change it when the AI-native workflow needs it.
Upstream tracking is a maintenance process, not a limit on features.

## Parts

| Part | Where | Owner |
| --- | --- | --- |
| Upstream Godot | every file from the 4.7.2-stable tag | The Godot project |
| gai engine features | engine files claimed by a feature | This repository |
| gai workspace | `bin/gai`, `AGENTS.md`, `docs/gai`, `.agents`, `game` | This repository |
| Your game | `game/` | You and your agent |

## First run

The user clones the repo, opens pi or opencode, and describes a game. The agent
runs `bin/gai bootstrap`, which builds the gai engine from source if needed and
checks the game. The user does not run setup commands.

## Features own gai's divergence

gai's engine changes belong to features in `.gai/features/`. Your game can edit
the engine directly; those changes show as unclaimed in the report.

```json
{
  "title": "Engine agent bridge",
  "status": "active",
  "risk": "medium",
  "paths": ["modules/gai_agent/"],
  "docs": ["docs/gai/features/agent-bridge.md"],
  "tests": ["tests/test_agent.py"]
}
```

- `active` features own their paths. `bin/gai upstream check` accepts changes
  there.
- `planned` features reserve paths but do not own them. Set `status` to `active`
  before the first edit that gai should maintain.
- `risk` is the expected conflict cost at the next upstream merge. High-risk
  features need a build and a test after every merge.

`bin/gai upstream check` warns when an engine path has no feature owner.
`--strict` fails, and gai's canonical CI uses it. A game can edit the engine
without a feature; `bin/gai upstream report` lists the unclaimed paths and the
merge risk.

## Upstream tracking

`main` merges Godot tags. The base is in `.gai/upstream.json`. A deep fork
conflicts on every release. The feature that claims a file resolves its conflict,
then rebuilds and reruns its tests. See `upstream.md`.

Rebase rewrites public history. Vendoring loses ancestry. Merge keeps both.

## The AI-native center

The engine must be usable by an agent, not only by a person with a mouse. The
engine agent bridge exposes the engine's own reflection and object handles:

- every class, property, method, signal, and singleton through `ClassDB` and
  `Object`;
- scene, node, resource, project, run, input, and screenshot methods;
- runtime and editor modes.

`bin/gai mcp` serves the same bridge over MCP on stdin/stdout. It is an adapter
process, not engine code.

An agent needs no new wrapper when the engine exposes a feature through
`ClassDB` or a singleton. It discovers with `classdb.classes`, inspects with
`object.properties/methods/signals`, and calls with `object.call`. The design is
in `features/agent-bridge.md`.

## Build gate

A deep fork must build. `bin/gai build` builds the engine and `bin/gai check`
tests the game, not the engine. An engine feature is not done until the engine
builds and its tests pass. The `engine` CI job builds the engine, runs the
bridge, MCP, game, and Steam tests, and checks that the binary is current.

## Branding

The `branding` feature claims `version.py` and sets `name = "gai"`. The binary
name and `short_name` stay `godot` while the build system depends on them. Full
UI branding is a feature, not a one-off edit.

## What check proves

Godot exits 0 on script errors. `bin/gai check` imports assets, parses every
script, runs the main scene, and runs `game/tests` when the runner exists. It
also refuses an engine or `version.py` that does not match the base tag. This is
the game gate.

## Limits

- The game lives in `game/`. The repository root is not a Godot project.
- A shallow clone cannot run `upstream check`.
- The .NET web export is planned, not implemented. It needs a custom engine
  build.
- The agent bridge exposes native runtime and editor reflection. GDScript
  `class_name` classes are reached through handles. It supports up to 8 clients
  and signal event subscriptions. Event replay, batch requests, export helpers,
  and headless screenshots are not implemented.
- The bridge token grants full local access, including `OS.execute`. It is not a
  sandbox.
- Steam is a native module. The Steamworks SDK is installed separately and is
  not committed. A clone without it builds and runs without Steam.
