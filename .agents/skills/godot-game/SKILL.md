---
name: godot-game
description: Build and change the Godot 4.7 game in this gai repository. Use for scenes, GDScript, input, UI, assets, or when `bin/gai check` fails.
---

# Build the game

The game is in `game/`. The agent contract is in `AGENTS.md` at the repository
root. Read it before you change files.

## Start

1. Run `bin/gai doctor`.
2. Read `game/project.godot` to learn the main scene, window size, and input actions.
3. List `game/` before you add files.

## Change a scene

Scenes are text files. Read the scene before you edit it.

To add a script to a scene:

1. Write the script.
2. Add one `ext_resource` line with a new id.
3. Add `script = ExtResource("your_id")` to the node.

```text
[gd_scene format=3]

[ext_resource type="Script" path="res://scripts/player.gd" id="1_player"]

[node name="Player" type="CharacterBody2D"]
script = ExtResource("1_player")
```

Keep the existing `uid://` values and node `unique_id` values. Godot writes them
to keep references stable. Do not invent new ones.

To add a node, add a `[node ...]` block with the parent path and set only the
properties you need. Keep the scene tree small and readable.

After a scene edit, run `bin/gai check`. A malformed scene fails the import or
the run step.

See `references/scene-format.md` for the fields that matter.

## Write GDScript

Use typed GDScript 2.0. Tabs for indentation.

```gdscript
extends CharacterBody2D

@export var speed: float = 200.0
@onready var sprite: Sprite2D = $Sprite2D

func _physics_process(_delta: float) -> void:
	var direction: Vector2 = Input.get_vector("left", "right", "up", "down")
	velocity = direction * speed
	move_and_slide()
```

Rules:

- Use `@export` for values a human should tune in the editor.
- Use `@onready` for nodes in the current scene.
- Use `%Name` only after you set `unique_name_in_owner = true` on the node.
- Emit signals with `hit.emit(3)`, not `emit_signal("hit", 3)`.
- Use `await get_tree().create_timer(0.5).timeout` for delays.
- Use `queue_free()` to remove a node. Do not touch it afterwards.
- Keep game state in a node or a resource. Do not use a global variable through an autoload unless `project.godot` declares it.

## Input

`Input.is_action_pressed("jump")` needs an action named `jump` in
`project.godot`. To add one, use the editor, or copy the shape of an existing
action. An action that is not declared prints
`ERROR: The InputMap action "jump" doesn't exist.` and `bin/gai check` fails.

For a one-off event, use `_unhandled_input(event: InputEvent)` and
`event.is_action_pressed("jump")`.

## UI and layout

- Use a `Control` root for a menu, and anchors instead of fixed offsets where the window can resize.
- Use a `CanvasLayer` for a HUD over a 2D scene.
- Set `mouse_filter = 2` on a label that must not block clicks.
- Connect a `Button` with `button.pressed.connect(_on_button_pressed)`.

## Assets

- Put source assets in `game/`. Keep the `.import` sidecar files that Godot creates.
- Do not commit `game/.godot/`.
- After you add or move an asset, run `bin/gai check` so Godot imports it.
- Use `res://` paths.
- Prefer an `.svg` for a simple icon. Godot imports SVG.

## Find and fix errors

1. Run `bin/gai check`.
2. Open `.gai/logs/check.log`.
3. Fix the first `SCRIPT ERROR` or `ERROR` line. Later errors are often a result of the first one.
4. Run `bin/gai check` again.

See `references/errors.md` for common messages.

## Test gameplay

`bin/gai check` runs `game/tests` when `game/tests/run_tests.gd` exists. Use
`bin/gai test --filter <name>` while you iterate.

A test extends the base class by path:

```gdscript
extends "res://tests/gai_test_case.gd"

func test_player_starts_alive() -> void:
	var player := auto_free(preload("res://player.tscn").instantiate())
	assert_eq(player.health, 3)

func test_jump_emits_signal() -> void:
	var player := auto_free(preload("res://player.tscn").instantiate())
	watch_signal(player, &"jumped")
	await frames(2)
	assert_signal_emitted(player, &"jumped")
```

- A `test_*` method runs once. Assertions record a failure and return false;
  return early when a later step needs the value.
- Use the base class assertions, not GDScript's `assert()`.
- `before_each()` and `after_each()` run around each test.
- `auto_free(node)` adds the node to the tree and frees it after the test.
- `await frames(n)`, `await physics_frames(n)`, and `await seconds(s)` wait.
- `await wait_until(callable)` waits for a condition; assert on its result.
- `pending("reason")` marks a test pending; call `return` after it.
- Input: `action_down/up`, `key_down/up`, `mouse_down/up`, `click`. The helpers
  send events and update `Input`; `_gai_reset` releases them.
- Doubles: `var player = double("res://player.gd")`, then
  `stub(player, "take_damage", 0)` and `assert_called(player, "take_damage", [2])`.
  A `Node` double needs `auto_free`. Use `double_scene("res://player.tscn")`
  when the test needs the scene's child nodes.
- `bin/gai test --isolate-tests --file-timeout 30` bounds one hung test.
- Do not override `_gai_*` methods. Read `docs/gai/testing.md`.

## Do not

- Do not hand-edit `game/.godot/`.
- Do not add a binary `.res` file by hand. Use text `.tres` files.
- Do not claim visual correctness. You cannot see the window.
- Do not edit the engine for a game task.
