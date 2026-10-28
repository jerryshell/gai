extends "res://tests/gai_test_case.gd"
## Tests for the input helpers. Replace them with tests for your game.


class InputProbe extends Node:
	var events: int = 0

	func _input(_event: InputEvent) -> void:
		events += 1


func test_action_state() -> void:
	action_down(&"ui_accept")
	await frames(2)
	assert_true(Input.is_action_pressed(&"ui_accept"), "action is pressed")
	action_up(&"ui_accept")
	await frames(2)
	assert_false(Input.is_action_pressed(&"ui_accept"), "action is released")


func test_event_dispatch() -> void:
	var probe := auto_free(InputProbe.new())
	action_down(&"ui_accept")
	await frames(2)
	assert_true(probe.events > 0, "input event reached _input")
	action_up(&"ui_accept")


func test_key_and_mouse() -> void:
	key_down(KEY_A)
	await frames(2)
	assert_true(Input.is_key_pressed(KEY_A), "key is pressed")
	key_up(KEY_A)
	await frames(2)
	assert_false(Input.is_key_pressed(KEY_A), "key is released")

	mouse_down(MOUSE_BUTTON_LEFT, Vector2(10, 10))
	await frames(2)
	assert_true(Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT), "mouse is pressed")
	mouse_up(MOUSE_BUTTON_LEFT, Vector2(10, 10))
	await frames(2)
	assert_false(Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT), "mouse is released")


class NodeProbe extends Node:
	var events: int = 0

	func _input(_event: InputEvent) -> void:
		events += 1


class GuiProbe extends Control:
	var events: int = 0

	func _gui_input(_event: InputEvent) -> void:
		events += 1


func test_target_node() -> void:
	var probe := auto_free(NodeProbe.new())
	action_down(&"ui_accept", 1.0, probe)
	action_up(&"ui_accept", probe)
	assert_eq(probe.events, 2, "both events reached the target node")


func test_target_control() -> void:
	var probe := auto_free(GuiProbe.new())
	mouse_down(MOUSE_BUTTON_LEFT, Vector2(1, 1), probe)
	mouse_up(MOUSE_BUTTON_LEFT, Vector2(1, 1), probe)
	assert_eq(probe.events, 2, "both events reached the target control")
