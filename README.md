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

The agent reads `AGENTS.md`, builds the gai engine from source on the first run,
and works in `game/`. It runs `bin/gai bootstrap` for you. You do not need to run
setup commands.

The first build needs SCons and a C++ toolchain. It can take 20 to 70 minutes
depending on the machine, and the agent tells you before it starts. The clone
carries the full Godot history, about 1.2 GB in `.git`. That history is what
makes upstream merges possible.

For manual use, run `bin/gai bootstrap`; it builds the engine if it is missing.
Then run `bin/gai run` or `bin/gai editor`. On Windows, run `python bin/gai` in
place of `bin/gai`.

If the machine cannot build, `bin/gai engine install` downloads the official
Godot 4.7.2 binary as a fallback. That binary has no gai display name and no
agent bridge. `bin/gai bootstrap --official` uses it.

## Use gai with a game outside this repository

Set `GAI_GAME` to a Godot project. `check`, `run`, `editor`, `agent`, and
`export web` use it. Runtime state stays in `<game>/.gai`, so the engine
repository stays clean.

```sh
GAI_GAME=/path/to/game bin/gai check
GAI_GAME=/path/to/game bin/gai check --scene res://level.tscn
GAI_GAME=/path/to/game bin/gai export web --clean --gzip
```

## What an agent gets

- `AGENTS.md` holds the workflow, the commands, and the Godot rules that agents
  get wrong.
- `.agents/skills/godot-game/` holds scene formats, GDScript patterns, and an
  error catalog. Pi and other Agent Skills tools load it when a task needs it.
- `bin/gai check` imports assets, parses every script, runs the main scene, and
  fails on errors. Godot exits 0 on a script error. This command does not. It
  also fails when the engine does not match the recorded upstream base.
- `bin/gai agent` starts the game or editor and exposes the engine's
  reflection: every class, property, method, signal, and singleton through
  handles, plus scene, node, resource, project, run, input, and screenshot
  methods. `agent call` reaches any method. The gai source build includes it;
  the official fallback does not.
- `bin/gai steam` builds [GodotSteam](https://godotsteam.com) into the engine.
  `Steam` is a native singleton, so the bridge reaches it like any other class.
  The Steamworks SDK is installed separately and is not committed. Design:
  `docs/gai/features/steam.md`.
- `game/` holds a small 2D scene that runs. Replace it.

## Deep fork, not a thin layer

The clone contains the whole engine source. The agent can read it and change any
file when a game requirement needs it. `bin/gai bootstrap` rebuilds the engine
after an engine change.

gai's own engine changes are tracked by features in `.gai/features/`. Your game
can also change engine files; those changes show as unclaimed in
`bin/gai upstream report`. `bin/gai upstream check` warns about them. gai's
canonical CI runs `--strict`; your clone does not.

Upstream merges are expected to conflict. The feature that owns a file resolves
its conflict, or you resolve it as a game change, then rebuild and rerun the
tests. See `docs/gai/upstream.md`.

## What is here

| Path | What it is |
| --- | --- |
| `game/` | Your Godot project. |
| engine source | Godot 4.7.2-stable, plus the active gai engine changes. |
| `.gai/` | gai metadata: version, upstream base, feature manifests, ownership rules. |
| `bin/gai` | The command line. Python 3.8 or later, no dependencies. |
| `docs/gai/` | Architecture, upstream sync, build, features, and decisions. |

## Roadmap

- **Engine agent bridge.** Runtime and editor reflection work: every native
  class, property, method, signal, and singleton is reachable. Event streams,
  signal connections, export helpers, and multiple clients are planned. Design:
  `docs/gai/features/agent-bridge.md`.
- **C# .NET web export.** Upstream 4.7.2 refuses it. The available patch targets
  4.8-dev and Windows. It needs a custom engine build. Design:
  `docs/gai/features/dotnet-web.md`.
- **Full branding.** Editor icon, splash, and UI strings.

## Status

Version 0.1.0. The display name is gai. Internal identifiers and the binary name
stay `godot` while the build system depends on them. The editor icon, splash,
and UI strings are still Godot. The agent bridge exposes the engine's reflection in runtime and editor
modes. It works in the gai source build, which `bootstrap` builds by default.
The official fallback lacks it. The token holder has full local access, so gai
is not a sandbox. Screenshots need a display. Event streams, signal
connections, export helpers, and the .NET web export are not implemented.

Tested on Linux. The macOS and Windows install paths are implemented but not
tested in this release.

gai is not affiliated with the Godot Foundation. See `NOTICE.md`.

## License

MIT, like Godot. See `LICENSE.txt`.
