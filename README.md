# gai

Godot, but AI Native.

gai is a deep fork of Godot 4.7.2, built around agents. The engine source is
here, a starter game is in `game/`, and pi or opencode can work on it from the
first minute. We change the engine where the agent workflow needs it. gai is not
a thin patch over Godot.

## Start

```sh
git clone git@github.com:jerryshell/gai.git my-game
# Without an SSH key:
# git clone https://github.com/jerryshell/gai.git my-game
cd my-game
pi
# or: opencode
```

Describe the game you want. For example:

> Build a 2D platformer about a cat that collects stars. Start with movement and one level.

The agent reads `AGENTS.md`, installs the engine on the first run, and works in
`game/`. It runs `bin/gai bootstrap` for you. You do not need to run setup
commands.

The first run downloads the official Godot 4.7.2 binary (about 140 MB) and checks
its SHA-512. The clone carries the full Godot history, about 1.2 GB in `.git`.
That history is what makes upstream merges possible.

For manual use, run `bin/gai bootstrap`. Then run `bin/gai run` or
`bin/gai editor`. On Windows, run `python bin/gai` in place of `bin/gai`.

## What an agent gets

- `AGENTS.md` holds the workflow, the commands, and the Godot rules that agents
  get wrong.
- `.agents/skills/godot-game/` holds scene formats, GDScript patterns, and an
  error catalog. Pi and other Agent Skills tools load it when a task needs it.
- `bin/gai check` imports assets, parses every script, runs the main scene, and
  fails on errors. Godot exits 0 on a script error. This command does not. It
  also fails when the engine does not match the recorded upstream base.
- `bin/gai agent start/tree/get/set` inspects and edits a running headless game.
  It needs a source build with `modules/gai_agent/`. The downloaded engine does
  not include it.
- `game/` holds a small 2D scene that runs. Replace it.

## Deep fork, not a thin layer

Every engine change belongs to a feature in `.gai/features/`. Active features
own their paths. `bin/gai upstream check` fails on an engine path with no owner,
not on the change itself. `bin/gai upstream report` lists the features, the
changed paths, and the unclaimed paths.

Upstream merges are expected to conflict. The feature that owns a file resolves
its conflict, rebuilds the engine, and reruns its tests. See
`docs/gai/upstream.md`.

## What is here

| Path | What it is |
| --- | --- |
| `game/` | Your Godot project. |
| engine source | Godot 4.7.2-stable, plus the active gai engine changes. |
| `.gai/` | gai metadata: version, upstream base, feature manifests, ownership rules. |
| `bin/gai` | The command line. Python 3.8 or later, no dependencies. |
| `docs/gai/` | Architecture, upstream sync, build, features, and decisions. |

## Roadmap

- **Engine agent bridge.** The headless runtime bridge works: scene tree,
  node get, and node set. Run control, input, screenshots, logs, test scenes,
  and editor mode are planned. Design: `docs/gai/features/agent-bridge.md`.
- **C# .NET web export.** Upstream 4.7.2 refuses it. The available patch targets
  4.8-dev and Windows. It needs a custom engine build. Design:
  `docs/gai/features/dotnet-web.md`.
- **Full branding.** Editor icon, splash, and UI strings.

## Status

Version 0.1.0. The display name is gai. Internal identifiers and the binary name
stay `godot` while the build system depends on them. The editor icon, splash,
and UI strings are still Godot. The agent bridge works in a source build for
headless scene inspection and node edits. Run control, input, screenshots,
editor mode, and the .NET web export are not implemented.

Tested on Linux. The macOS and Windows install paths are implemented but not
tested in this release.

gai is not affiliated with the Godot Foundation. See `NOTICE.md`.

## License

MIT, like Godot. See `LICENSE.txt`.
