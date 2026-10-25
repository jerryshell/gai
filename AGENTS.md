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
- After an engine change, rebuild with `bin/gai bootstrap` and run `bin/gai check`.
  Read `docs/gai/upstream.md` for the merge risk.

## Commands

Run these from the repository root.

| Command | What it does |
| --- | --- |
| `bin/gai bootstrap` | Builds the gai engine if needed, then checks the game. Use this on the first run. |
| `bin/gai doctor` | Checks the engine, the game, features, and the upstream base. |
| `bin/gai check` | Imports assets, parses every `.gd` file, runs the main scene headless, and fails on errors. |
| `bin/gai run -- <args>` | Runs the game. Add `--headless` for a test run without a window. |
| `bin/gai editor` | Opens the editor. A human uses this command. |
| `bin/gai agent start` | Starts the headless game with the live scene bridge. Requires a source build. |
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

`agent start --editor` starts the editor, where `EditorInterface` is a
singleton. In editor mode `run.*`, `scene.change`, and `input.*` need
`force: true`; `scene.tree` returns the edited scene when one is open. Add
`--display` for screenshots. The token holder has full local access, including
`OS.execute`.

## The loop

1. Read the task and inspect `game/`.
2. Make the smallest change that completes it.
3. Run `bin/gai check`. It must exit 0.
4. If it fails, read `.gai/logs/check.log`, fix the first error, and run it again.

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
- You cannot see the game window. Never claim that a scene looks right. Say what you changed and what the check proves.
- For logic that is hard to observe, add a temporary `print()` and run `bin/gai run -- --headless --quit-after 60`.
- Do not hide a failing check. Report it with the first error from the log.

## Engine work

The engine is fully editable. A game task starts in `game/`, but it may change
any engine file when the requirement needs it. After an engine change, rebuild
with `bin/gai bootstrap` and run `bin/gai check`.

For a change that gai itself should maintain:

1. Read `docs/gai/architecture.md` and `docs/gai/upstream.md`.
2. Add or activate a feature in `.gai/features/`.
3. Add the feature doc and tests.
4. Build the engine and run the feature tests.
5. Run `bin/gai upstream check --strict` before you commit.

A game-specific engine change can stay unclaimed. `bin/gai upstream report`
shows it and the merge risk. Ownership is for upstream maintenance, not
permission. The build and tests are the gate.

Godot 4.7 documentation: https://docs.godotengine.org/en/4.7/
