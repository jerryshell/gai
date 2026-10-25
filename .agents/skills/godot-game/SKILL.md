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
action. An action that is not declared does not raise an error.

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

## Do not

- Do not hand-edit `game/.godot/`.
- Do not add a binary `.res` file by hand. Use text `.tres` files.
- Do not claim visual correctness. You cannot see the window.
- Do not edit the engine for a game task.
