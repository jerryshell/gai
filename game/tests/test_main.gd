extends "res://tests/gai_test_case.gd"
## Example game tests. Replace them with tests for your game.


func test_main_scene_loads() -> void:
	var packed := load("res://scenes/main.tscn") as PackedScene
	assert_not_null(packed, "main scene loads")
	if packed == null:
		return
	var scene := packed.instantiate()
	auto_free(scene)
	assert_eq(scene.name, "Main")
	var title := scene.get_node_or_null("Title") as Label
	assert_not_null(title, "Title label exists")
	if title != null:
		assert_eq(title.text, "gai")


func test_signal_watcher_and_frames() -> void:
	var node := Node.new()
	watch_signal(node, &"ready")
	auto_free(node)
	await frames(1)
	assert_signal_emitted(node, &"ready")
	assert_signal_emit_count(node, &"ready", 1)
