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
runs `bin/gai bootstrap`, which installs the official engine if needed and
checks the game. The user does not run setup commands.

## Features own divergence

Every engine change belongs to a feature in `.gai/features/`:

```json
{
  "title": "Engine agent bridge",
  "status": "planned",
  "risk": "high",
  "paths": ["modules/gai_agent/", "main/main.cpp"],
  "docs": ["docs/gai/features/agent-bridge.md"],
  "tests": ["tests/gai_agent/"]
}
```

- `active` features own their paths. `bin/gai upstream check` accepts changes
  there.
- `planned` features reserve paths but do not own them. Set `status` to `active`
  before the first engine edit.
- `risk` is the expected conflict cost at the next upstream merge. High-risk
  features need a build and a test after every merge.

`bin/gai upstream check` fails when an engine path has no active feature. It does
not fail because the engine changed. The rule is ownership, not a size limit.
`bin/gai upstream report` lists features, changed paths, and unclaimed paths.

## Upstream tracking

`main` merges Godot tags. The base is in `.gai/upstream.json`. A deep fork
conflicts on every release. The feature that claims a file resolves its conflict,
then rebuilds and reruns its tests. See `upstream.md`.

Rebase rewrites public history. Vendoring loses ancestry. Merge keeps both.

## The AI-native center

The engine must be usable by an agent, not only by a person with a mouse. The
first vertical feature is the engine agent bridge:

- scene tree inspection and node edits;
- run, stop, and frame control;
- input injection;
- screenshots;
- log tail;
- test scenes.

`bin/gai` will be the client. The bridge will run inside the editor or the game,
bound to localhost with a token. The current CLI cannot see live editor state.
The bridge will close that gap. The design is in `features/agent-bridge.md`.

## Build gate

A deep fork must build. `docs/gai/build.md` has the commands. `bin/gai check`
tests the game, not the engine. An engine feature is not done until the engine
builds and its tests pass. The current CI does not build the engine yet. That is
the next infrastructure piece.

## Branding

The `branding` feature claims `version.py` and sets `name = "gai"`. The binary
name and `short_name` stay `godot` while the build system depends on them. Full
UI branding is a feature, not a one-off edit.

## What check proves

Godot exits 0 on script errors. `bin/gai check` imports assets, parses every
script, and runs the main scene. It also refuses an engine or `version.py` that
does not match the base tag. This is the game gate.

## Limits

- The game lives in `game/`. The repository root is not a Godot project.
- A shallow clone cannot run `upstream check`.
- The .NET web export is planned, not implemented. It needs a custom engine
  build.
- The engine agent bridge is planned, not implemented.
