# Scene format

A `.tscn` file is a text resource. Godot reads and writes the same format.

## Header

```text
[gd_scene load_steps=2 format=3 uid="uid://..."]
```

`format=3` is the Godot 4 format. `load_steps` is a hint. `uid` is the scene's
resource id. Keep an existing `uid`. Omit it on a new file.

## External resources

```text
[ext_resource type="Script" path="res://scripts/player.gd" id="1_player"]
```

`type` is the resource class. `path` uses `res://`. `id` is a local string and
must be unique in the file.

Omit `uid` on a new `ext_resource`. Godot resolves the path and writes the uid
the next time it saves the scene.

## Nodes

```text
[node name="Player" type="CharacterBody2D"]
script = ExtResource("1_player")

[node name="Sprite2D" type="Sprite2D" parent="."]
position = Vector2(0, -16)
```

The root node has no `parent`. A child uses `parent="."` or
`parent="Player/Sprite2D"`.

Property values use Godot's text syntax:

```text
Vector2(10, 20)
Color(0.1, 0.2, 0.3, 1)
"text"
true
ExtResource("1_player")
SubResource("CircleShape_1")
NodePath("../Player")
```

## Instance another scene

```text
[ext_resource type="PackedScene" path="res://scenes/enemy.tscn" id="2_enemy"]

[node name="Enemy" parent="." instance=ExtResource("2_enemy")]
```

Add properties below the node to override them on this instance.

## Sub-resources

```text
[sub_resource type="CircleShape2D" id="CircleShape_1"]
radius = 16.0
```

Reference it with `SubResource("CircleShape_1")`.

## Rules

- Keep ids stable. Do not reuse an id for a different resource.
- Keep `unique_id` on a node that has one.
- Do not add a script to a node before the script file exists.
- Run `bin/gai check` after every scene edit.
