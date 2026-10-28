# gai agent guide

gai is a deep fork of Godot 4.7.2, built around agents. The engine source is at
the repository root. Your game is in `game/`.

Read `docs/gai/architecture.md` before you change anything outside `game/`.

## First run

When the user describes a game, do this before you plan:

1. Run `bin/gai bootstrap`. It builds the gai engine from source if it is
   missing, then checks the game. The build needs SCons and a C++ toolchain and
   can take 20 to 70 minutes. Tell the user before it starts. If a build
   dependency is missing, install it or tell the user what is missing. Do not
   silently switch to the official fallback. On Windows, run
   `python bin/gai bootstrap`.
2. Read `game/project.godot` and `game/scenes/main.tscn`.
3. Start with the smallest playable slice. If the idea is vague, ask one short
   question about the core loop, then start.
4. Run `bin/gai check` after every change.
5. Open the editor only when the user asks. Use headless runs for your own tests.

Do not ask the user to install the engine, run `check`, or open the editor for
you. Do not present a long plan before the first playable change.

## Work in the game

- Put game code, scenes, and assets in `game/`. The engine source is part of your
  workspace: read it and change it when the game needs it.
- A game task does not edit the fork's front-door files (`README.md`,
  `version.py`, `.gitignore`) by default.
- Do not commit `game/.godot/`, `.gai/bin/`, or `.gai/logs/`.
- After an engine change, run `bin/gai build` and `bin/gai check`. Read
  `docs/gai/upstream.md` for the merge risk.

## Commands

Run these from the repository root.

| Command | What it does |
| --- | --- |
| `bin/gai bootstrap` | Builds the gai engine when it is missing or stale, then checks the game. Use this on the first run. |
| `bin/gai build` | Builds the gai engine from source. `--check` tests freshness; `--force` rebuilds; `--dry-run` prints the command. |
| `bin/gai doctor` | Checks the engine, the game, features, and the upstream base. |
| `bin/gai check` | Imports assets, parses every `.gd` file, runs the main scene and `game/tests`, and fails on errors. |
| `bin/gai test` | Runs `game/tests` headlessly. `check` runs it by default; `--no-tests` skips it. |
| `bin/gai run -- <args>` | Runs the game. Add `--headless` for a test run without a window. |
| `bin/gai editor` | Opens the editor. A human uses this command. |
| `bin/gai agent start` | Starts the headless game with the live scene bridge. Requires a source build. |
| `bin/gai agent watch` | Streams signal events from the bridge; pass `--path` or `--handle` and `--signal`. |
| `bin/gai mcp` | Serves the running bridge over MCP stdio. Add `--start` to start the game. |
| `bin/gai export web` | Exports a web build. Needs a `Web` preset and export templates. |
| `bin/gai steam status` | Shows the Steam module, the SDK, and the runtime library. |
| `bin/gai engine install` | Downloads the official fallback engine into `.gai/bin/`. It has no gai features. |
| `bin/gai upstream check` | Warns when an engine change has no feature owner; `--strict` fails. |
| `bin/gai upstream report` | Lists features, changed paths, and unclaimed paths. |

## Live scene

The agent bridge runs in the gai source build, which `bootstrap` builds by
default. The official fallback does not include it.

```sh
bin/gai agent start
bin/gai agent tree
bin/gai agent get /root/Main --property visible
bin/gai agent set /root/Main visible false
bin/gai agent methods
bin/gai agent call classdb.classes '{}'
bin/gai agent call classdb.class '{"name":"Node2D"}'
bin/gai agent call object.singleton '{"name":"PhysicsServer3D"}'
bin/gai agent call object.call '{"handle":"<handle>","method":"get_class","args":[]}'
bin/gai agent watch --path /root/Main/Title --signal visibility_changed
bin/gai agent stop
```

The bridge exposes the engine's reflection. Every native class, property,
method, signal, and singleton is reachable through `classdb.*`, `object.*`, and
`api.singletons`. GDScript `class_name` classes are reached through node or
object handles. A handle is the decimal string returned by `scene.tree`,
`object.singleton`, `classdb.instantiate`, or `resource.load`. Use
`agent call` for any method; the named commands are sugar.

A string stays a string when the target is a string; for non-string targets use
Godot text such as `Vector2(10, 20)`, or `{"$var": "..."}` inside a generic
dictionary. Pass an object as `{"$handle": "<id>"}`. An unknown handle is an
error. `object.free` only frees handles the bridge created; use `node.delete` for
tree nodes.

For an MCP client, `bin/gai mcp` serves the same bridge over stdio. Read
`docs/gai/mcp.md`.

`agent start --editor` starts the editor, where `EditorInterface` is a
singleton. In editor mode `run.*`, `scene.change`, and `input.*` need
`force: true`; `scene.tree` returns the edited scene when one is open. Add
`--display` for screenshots. The token holder has full local access, including
`OS.execute`.

## A game outside this repository

Set `GAI_GAME` to a Godot project outside this clone. `check`, `test`, `run`,
`editor`, `agent`, `mcp`, and `export web` use it. Runtime state goes to
`<game>/.gai`.

```sh
GAI_GAME=/path/to/game bin/gai check
GAI_GAME=/path/to/game bin/gai test
GAI_GAME=/path/to/game bin/gai check --scene res://level.tscn
GAI_GAME=/path/to/game bin/gai export web --clean --gzip
```

Projects with autoloads load every script in a scene, so autoload names
resolve. `--scene` exercises a gameplay scene when the main scene is only a
menu. Web export uses the official Godot web template; the agent bridge and
Steam are not in that runtime.

## Steam

The engine includes GodotSteam 4.23.2. `Steam` and `SteamProjectSettings` are
native singletons, so the bridge reaches them through `classdb.*` and
`object.*`. The Steamworks SDK 1.65 is installed separately and is never
committed:

```sh
bin/gai steam status
bin/gai steam sdk --download
```

Without the SDK the engine builds without Steam and prints why. Auto init is off
by default, so a headless run does not touch Steam. Do not commit
`modules/godotsteam/sdk/`.

If a project ships the GodotSteam GDExtension in `addons/godotsteam`, remove it.
The engine already has Steam built in, and the extension cannot register a
second `Steam` singleton. `bin/gai check` fails with that message. GodotSteam
rejects LLM-written patches upstream; keep changes local.

## The loop

1. Read the task and inspect `game/`.
2. Make the smallest change that completes it.
3. Add a test in `game/tests/test_*.gd` when the change has behavior a run does
   not show. Extend `res://tests/gai_test_case.gd`.
4. Run `bin/gai check`. It must exit 0.
5. If it fails, read `.gai/logs/check.log`, fix the first error, and run it again.

Godot exits 0 when a scene hits a script error, so never trust the game process
exit code by itself. `bin/gai check` scans the output and fails for you.

## Godot rules that agents get wrong

- GDScript 2.0 uses tabs. Do not mix tabs and spaces.
- Give variables and functions types. `var speed: float = 200.0`, `func hit() -> void:`.
- Use `@onready var label: Label = $Label` for children of the current scene.
- A node exists only after `add_child`. Do not call its methods before that.
- Scenes are text. Keep the `uid://` and `unique_id` values that Godot writes. Do not invent them.
- `res://` paths only. Never use an absolute filesystem path in the game.
- Declare input actions in `project.godot` before you call `Input.is_action_pressed`. An undeclared action prints an `ERROR:` line, and `bin/gai check` fails on it.
- Connect signals with `button.pressed.connect(_on_pressed)`. Emit them with `my_signal.emit(value)`.
- `queue_free()` is deferred. Do not use the node after you call it.
- Use `preload("res://...")` for a fixed resource and `load()` for a runtime path.
- Use `get_tree().change_scene_to_file("res://...")` to replace the scene.
- For 2D movement, use `CharacterBody2D`, set `velocity`, then call `move_and_slide()`.
- Keep `run/main_scene` in `project.godot` pointing at a scene that exists.
- Do not edit `game/.godot/`. It is a cache. Delete it if imports go stale, then run `bin/gai check`.

## Verification

- `bin/gai check` is the game gate. A clean run prints `check: ok`.
- `bin/gai check` runs `game/tests` when the runner exists. `bin/gai test --filter <name>` runs one area while you iterate. Read `docs/gai/testing.md`.
- You cannot see the game window. Never claim that a scene looks right. Say what you changed and what the check proves.
- For logic that is hard to observe, add a test that asserts the behavior. Use a temporary `print()` only when a test is not practical.
- Do not hide a failing check. Report it with the first error from the log.

## Engine work

The engine is fully editable. A game task starts in `game/`, but it may change
any engine file when the requirement needs it. After an engine change, rebuild
with `bin/gai build` and run `bin/gai check`.

For a change that gai itself should maintain:

1. Read `docs/gai/architecture.md` and `docs/gai/upstream.md`.
2. Add or activate a feature in `.gai/features/`.
3. Add the feature doc and tests.
4. Build the engine with `bin/gai build` and run the feature tests.
5. Run `bin/gai upstream check --strict` before you commit.

A game-specific engine change can stay unclaimed. `bin/gai upstream report`
shows it and the merge risk. Ownership is for upstream maintenance, not
permission. The build and tests are the gate.

Godot 4.7 documentation: https://docs.godotengine.org/en/4.7/
