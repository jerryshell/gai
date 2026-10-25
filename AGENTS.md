# gai agent guide

gai is Godot 4.7.2 with an AI-native workspace. The engine source is at the
repository root. Your game is in `game/`.

Read `docs/gai/architecture.md` before you change anything outside `game/`.

## Work in the game

- Put game code, scenes, and assets in `game/`.
- Do not edit the engine, `README.md`, `version.py`, or `.gitignore` for a game task.
- Do not commit `game/.godot/`, `.gai/bin/`, or `.gai/logs/`.
- When a task needs an engine change, stop and read `docs/gai/upstream.md` first.

## Commands

Run these from the repository root.

| Command | What it does |
| --- | --- |
| `bin/gai doctor` | Checks the engine, the game, and the upstream base. |
| `bin/gai check` | Imports assets, parses every `.gd` file, runs the main scene headless, and fails on errors. |
| `bin/gai run -- <args>` | Runs the game. Add `--headless` for a test run without a window. |
| `bin/gai editor` | Opens the editor. A human uses this command. |
| `bin/gai engine install` | Downloads official Godot 4.7.2 into `.gai/bin/`. |
| `bin/gai upstream check` | Fails when a commit changes a file outside the gai layer. |

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

- `bin/gai check` is the gate. A clean run prints `check: ok`.
- You cannot see the game window. Never claim that a scene looks right. Say what you changed and what the check proves.
- For logic that is hard to observe, add a temporary `print()` and run `bin/gai run -- --headless --quit-after 60`.
- Do not hide a failing check. Report it with the first error from the log.

## Engine changes

The engine is upstream Godot plus a thin gai layer. Read `docs/gai/upstream.md`
and run `bin/gai upstream check` before you commit any engine change. A change
outside the layer is a product decision, so ask the human first.

Godot 4.7 documentation: https://docs.godotengine.org/en/4.7/
