# Games outside the repository

gai can work on a Godot project that lives outside this clone. Set `GAI_GAME` to
the project directory. `check`, `test`, `run`, `editor`, `agent`, `mcp`,
`export`, and `init` use it. Runtime state goes to `<game>/.gai`, so the engine
repository stays clean.

```sh
GAI_GAME=/path/to/game bin/gai check
GAI_GAME=/path/to/game bin/gai test
GAI_GAME=/path/to/game bin/gai test --scene-dir res://tests
GAI_GAME=/path/to/game bin/gai check --scene res://level.tscn
GAI_GAME=/path/to/game bin/gai agent start
GAI_GAME=/path/to/game bin/gai export web --clean --gzip
GAI_GAME=/path/to/game bin/gai export linux --output build/linux/game.x86_64
```

The check log, the agent token, and the export log stay with the game. `bin/gai` itself, the upstream base, and the feature manifests
stay in the engine repository.

## Autoloads

`--check-only --script` does not load a project's autoloads. A script that names
`SignalBus` or `Global` fails there even when it is valid. When
`project.godot` has an `[autoload]` section, `check` writes a small scene under
`<game>/.gai/check`, runs it with the project's autoloads, and loads every `.gd`
script from it. The scene is removed after the check. Projects without autoloads
keep the per-script parse.

On a project without `.godot`, `check` imports twice. The first pass may print
load errors for assets that do not exist yet; the second pass is the gate.

Use `--scene` to run a gameplay scene after the main scene. The main scene may
only load a menu. The extra scene exercises the gameplay scripts.

## Add gai files

```sh
bin/gai init /path/to/game
```

`init` writes `AGENTS.md`, `docs/gai.md`, and `.gai/mcp.json`. It adds the
GDScript test harness when the project has no tests. When `tests/` already has
scene tests, it leaves them alone and writes the scene-test command instead.
Pass `--force` to replace generated files and `--no-mcp` to skip the MCP config.

## Scene tests

```sh
GAI_GAME=/path/to/game bin/gai test --scene-dir res://tests
```

Each `.tscn` runs in its own engine process. The report goes to
`.gai/logs/scene-test.xml` and the log to `.gai/logs/scene-test.log`.

## Windows and Linux export

```sh
GAI_GAME=/path/to/game bin/gai export linux --output build/linux/game.x86_64
GAI_GAME=/path/to/game bin/gai export windows --output build/windows/game.exe \
  --archive build/game-windows.zip --checksum
```

The command reads `export_presets.cfg`, checks a custom template if the preset
sets one, exports, copies the Steam runtime when the SDK has it, and can write
an archive and `SHA256SUMS`. `--dry-run` prints the export command after
preflight. `--steam-runtime` requires the runtime; `--no-steam-runtime` skips
it.

## Web export

Add a `Web` preset to the project's `export_presets.cfg`. Then:

```sh
bin/gai export web --clean --gzip
```

The command finds the matching official export templates, exports to
`build/web/index.html`, writes `.gdignore` in the output so Godot does not
import the exported files, and with `--gzip` writes `.gz` files for a static
server with `gzip_static`. It checks that `index.html`, `index.wasm`, and
`index.pck` exist.

The gai engine currently uses Godot's official web template. The web runtime is
stock Godot, so gai modules such as the agent bridge and Steam are not in it.
A custom gai web template needs Emscripten and is not built yet.
