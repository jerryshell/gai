extends RefCounted
## Base class for gai game tests.
##
## Extend it by path:
##
## [codeblock]
## extends "res://tests/gai_test_case.gd"
##
## func test_player_starts_alive() -> void:
##     var player: Player = auto_free(Player.new())
##     assert_eq(player.health, 3)
## [/codeblock]
##
## Every method whose name starts with [code]test_[/code] runs once. Assertions
## record a failure and return false; a test continues after a failed assertion.
## Return early when later steps depend on an earlier one.

const MAX_SIGNAL_ARGS: int = 6

var failures: Array[String] = []
var pending_reason: String = ""

var _auto_free_nodes: Array[Node] = []
var _watchers: Array[Dictionary] = []
var _signal_counts: Dictionary = {}
var _double_calls: Dictionary = {}
var _double_stubs: Dictionary = {}
var _pressed_actions: Array[StringName] = []
var _pressed_keys: Array[int] = []
var _pressed_buttons: Array[int] = []


func _gai_test_case() -> bool:
	return true


## The running [SceneTree]. Tests run as a SceneTree script.
func tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree


## Add a node to the running scene when it has no parent, and free it after
## the test.
func auto_free(node: Node) -> Node:
	_auto_free_nodes.append(node)
	var scene_tree := tree()
	if scene_tree != null and node.get_parent() == null:
		scene_tree.root.add_child(node)
	return node


## Alias used by GUT-style tests.
func add_child_autofree(node: Node) -> Node:
	return auto_free(node)


## Wait for [param count] process frames. Use [code]await frames(1)[/code].
func frames(count: int = 1) -> void:
	for _index in count:
		await tree().process_frame


## Wait for [param count] physics frames. Use [code]await physics_frames(1)[/code].
func physics_frames(count: int = 1) -> void:
	for _index in count:
		await tree().physics_frame


## Wait until [param predicate] returns true, or [param timeout] seconds pass.
## Returns true when the predicate became true. The predicate is checked once
## before the first frame.
func wait_until(predicate: Callable, timeout: float = 1.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(timeout * 1000.0)
	while true:
		if bool(predicate.call()):
			return true
		if Time.get_ticks_msec() >= deadline:
			return false
		await tree().process_frame
	return false


## Wait for [param duration] seconds. Use [code]await seconds(0.1)[/code].
func seconds(duration: float) -> void:
	await tree().create_timer(duration).timeout


## Record a failure. Prefer an assert method.
func fail(message: String) -> void:
	failures.append(message)


## Mark this test as pending. Call [code]return[/code] after it.
func pending(reason: String = "") -> void:
	pending_reason = reason if not reason.is_empty() else "pending"


func get_failures() -> Array[String]:
	return failures


func get_pending_reason() -> String:
	return pending_reason


# Doubles, spies, and stubs.

## Build a script that extends [param path] and records calls to its methods.
## [param methods] limits the overridden methods; an empty array overrides every
## eligible method. Set the instance's [code]__gai_test[/code] property to this
## test, or use [method double]. A plain object cannot be spied; use a double.
func double_script(path: String, methods: Array[String] = []) -> GDScript:
	var base_script := load(path) as GDScript
	if base_script == null:
		fail("double_script: cannot load " + path)
		return null
	var wanted := {}
	for method_name in methods:
		wanted[method_name] = true
	var source := "extends " + var_to_str(path) + "\n\nvar __gai_test: Object = null\n\n"
	var generated := 0
	var seen := {}
	for info in base_script.get_script_method_list():
		var name := String(info["name"])
		seen[name] = true
		if not methods.is_empty() and not wanted.has(name):
			continue
		var block := _double_method(info)
		if block.is_empty():
			if not methods.is_empty():
				fail("double_script: cannot override %s on %s" % [name, path])
				return null
			continue
		source += block + "\n"
		generated += 1
	for method_name in methods:
		if not seen.has(method_name):
			fail("double_script: %s has no method %s" % [path, method_name])
			return null
	if generated == 0:
		fail("double_script: no methods to override on " + path)
		return null
	var doubled := GDScript.new()
	doubled.source_code = source
	var error := doubled.reload()
	if error != OK:
		fail("double_script: cannot compile the double for " + path)
		return null
	return doubled


## Create a doubled instance of the script at [param path] and connect it to
## this test. A Node double must be passed to [method auto_free].
func double(path: String, methods: Array[String] = []) -> Object:
	var script := double_script(path, methods)
	if script == null:
		return null
	var instance: Object = script.new()
	if instance == null:
		fail("double: cannot instantiate " + path)
		return null
	instance.set("__gai_test", self)
	return instance


## Make a doubled method return [param value]. Pass [param args] to match one
## argument list, or null to match every call.
func stub(object: Object, method_name: StringName, value: Variant, args: Variant = null) -> void:
	if object == null:
		fail("stub: object is null")
		return
	var key := _double_key(object, method_name)
	if not _double_stubs.has(key):
		_double_stubs[key] = {}
	var stubs: Dictionary = _double_stubs[key]
	stubs["" if args == null else var_to_str(args)] = value


## Every recorded argument list for one method, in call order.
func get_calls(object: Object, method_name: StringName) -> Array:
	if object == null:
		return []
	var calls: Array = _double_calls.get(_double_key(object, method_name), [])
	return calls.duplicate(true)


## Assert that a doubled method was called. Pass [param args] to match one
## argument list, or null to match any call.
func assert_called(
	object: Object, method_name: StringName, args: Variant = null, message: String = ""
) -> bool:
	var count := _call_count(object, method_name, args)
	if count > 0:
		return true
	return _fail(
		"expected %s.%s to be called%s%s"
		% [object, method_name, _args_suffix(args), _suffix(message)]
	)


## Assert that a doubled method was not called.
func assert_not_called(
	object: Object, method_name: StringName, args: Variant = null, message: String = ""
) -> bool:
	var count := _call_count(object, method_name, args)
	if count == 0:
		return true
	return _fail(
		"expected %s.%s not to be called%s, but it was called %d times%s"
		% [object, method_name, _args_suffix(args), count, _suffix(message)]
	)


## Assert the number of calls to a doubled method.
func assert_call_count(
	object: Object,
	method_name: StringName,
	expected: int,
	args: Variant = null,
	message: String = ""
) -> bool:
	var count := _call_count(object, method_name, args)
	if count == expected:
		return true
	return _fail(
		"expected %s.%s to be called %d times%s, got %d%s"
		% [object, method_name, expected, _args_suffix(args), count, _suffix(message)]
	)


func _double_key(object: Object, method_name: StringName) -> String:
	return "%d:%s" % [object.get_instance_id(), method_name]


func _gai_double_record(object: Object, method_name: StringName, args: Array) -> void:
	var key := _double_key(object, method_name)
	if not _double_calls.has(key):
		_double_calls[key] = []
	(_double_calls[key] as Array).append(args.duplicate())


func _gai_double_stub(object: Object, method_name: StringName, args: Array) -> Dictionary:
	var key := _double_key(object, method_name)
	if not _double_stubs.has(key):
		return {"stubbed": false}
	var stubs: Dictionary = _double_stubs[key]
	var exact := var_to_str(args)
	if stubs.has(exact):
		return {"stubbed": true, "value": stubs[exact]}
	if stubs.has(""):
		return {"stubbed": true, "value": stubs[""]}
	return {"stubbed": false}


func _call_count(object: Object, method_name: StringName, args: Variant) -> int:
	var calls := get_calls(object, method_name)
	if args == null:
		return calls.size()
	var needle := var_to_str(args)
	var count := 0
	for call_args in calls:
		if var_to_str(call_args) == needle:
			count += 1
	return count


func _args_suffix(args: Variant) -> String:
	return "" if args == null else " with " + var_to_str(args)


func _double_method(info: Dictionary) -> String:
	var name := String(info["name"])
	if name.is_empty() or name.begins_with("_") or name.begins_with("@"):
		return ""
	if name.begins_with("__gai_"):
		return ""
	if not _is_identifier(name):
		return ""
	var flags := int(info.get("flags", 1))
	if flags & 2 != 0 or flags & 4 != 0 or flags & 8 != 0:
		return ""
	var args: Array = info.get("args", [])
	var defaults: Array = info.get("default_args", [])
	if defaults.size() > args.size():
		return ""
	var default_start := args.size() - defaults.size()
	var used := {}
	var names: Array[String] = []
	var params: Array[String] = []
	for index in args.size():
		var arg_info: Dictionary = args[index]
		var raw_name := String(arg_info.get("name", ""))
		var arg_name := _argument_name(raw_name, index, used)
		var param := arg_name
		if index >= default_start:
			var default_value: Variant = defaults[index - default_start]
			var arg_type := int(arg_info.get("type", 0))
			var literal := ""
			if default_value is Dictionary and (default_value as Dictionary).is_empty():
				literal = "{}"
			elif default_value == null:
				match arg_type:
					0, 24:
						literal = "null"
					27:
						literal = "{}"
					28:
						literal = "[]"
					_:
						return ""
			else:
				literal = var_to_str(default_value)
			if literal.is_empty() or literal.begins_with("<") or literal.contains("\n"):
				return ""
			param += " = " + literal
		names.append(arg_name)
		params.append(param)
	var args_text := ", ".join(names)
	var params_text := ", ".join(params)
	var return_info: Dictionary = info.get("return", {})
	var is_void := int(return_info.get("type", 0)) == 0 and int(return_info.get("usage", 0)) == 0
	var lines := PackedStringArray()
	lines.append("func %s(%s):" % [name, params_text])
	lines.append("\tif __gai_test != null:")
	lines.append("\t\t__gai_test._gai_double_record(self, %s, [%s])" % [var_to_str(name), args_text])
	lines.append(
		"\t\tvar __gai_stub: Dictionary = __gai_test._gai_double_stub(self, %s, [%s])"
		% [var_to_str(name), args_text]
	)
	lines.append("\t\tif __gai_stub.get(\"stubbed\", false):")
	if is_void:
		lines.append("\t\t\treturn")
	else:
		lines.append("\t\t\treturn __gai_stub.get(\"value\")")
	lines.append("\treturn super(%s)" % args_text)
	return "\n".join(lines)


func _argument_name(raw: String, index: int, used: Dictionary) -> String:
	var name := raw
	if not _is_identifier(name) or _is_keyword(name) or name.begins_with("__gai_"):
		name = "arg%d" % index
	while used.has(name):
		name += "_"
	used[name] = true
	return name


func _is_identifier(value: String) -> bool:
	if value.is_empty():
		return false
	var first := value.unicode_at(0)
	if not _is_identifier_start(first):
		return false
	for index in range(1, value.length()):
		var code := value.unicode_at(index)
		if not _is_identifier_start(code) and not (code >= 48 and code <= 57):
			return false
	return true


func _is_identifier_start(code: int) -> bool:
	return (code >= 65 and code <= 90) or (code >= 97 and code <= 122) or code == 95


func _is_keyword(value: String) -> bool:
	return value in [
		"and", "as", "assert", "await", "break", "breakpoint", "class", "class_name",
		"const", "continue", "elif", "else", "enum", "extends", "false", "for", "func",
		"if", "in", "is", "match", "not", "null", "or", "pass", "preload", "return",
		"self", "signal", "static", "super", "true", "var", "void", "when", "while", "yield",
	]


# Input.

## Send [param event] through the engine, or to [param target] only.
func send_event(event: InputEvent, target: Node = null) -> void:
	if target == null:
		Input.parse_input_event(event)
		return
	if target is Control:
		target.call("_gui_input", event)
	elif target is Viewport:
		target.call("push_input", event)
	else:
		if target.has_method("_input"):
			target.call("_input", event)
		if target.has_method("_unhandled_input"):
			target.call("_unhandled_input", event)


## Press an input action. Release it with [method action_up].
func action_down(action: StringName, strength: float = 1.0, target: Node = null) -> void:
	var event := InputEventAction.new()
	event.action = action
	event.pressed = true
	event.strength = strength
	send_event(event, target)
	if target == null:
		Input.action_press(action, strength)
	if not _pressed_actions.has(action):
		_pressed_actions.append(action)


## Release an input action.
func action_up(action: StringName, target: Node = null) -> void:
	var event := InputEventAction.new()
	event.action = action
	event.pressed = false
	event.strength = 0.0
	send_event(event, target)
	if target == null:
		Input.action_release(action)
	_pressed_actions.erase(action)


## Press and release an input action in one call.
func action_press(action: StringName, strength: float = 1.0, target: Node = null) -> void:
	action_down(action, strength, target)
	action_up(action, target)


## Press a key. Release it with [method key_up].
func key_down(keycode: int, target: Node = null) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = true
	send_event(event, target)
	if not _pressed_keys.has(keycode):
		_pressed_keys.append(keycode)


## Release a key.
func key_up(keycode: int, target: Node = null) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = false
	send_event(event, target)
	_pressed_keys.erase(keycode)


## Press a mouse button. Release it with [method mouse_up].
func mouse_down(button: int = MOUSE_BUTTON_LEFT, position: Vector2 = Vector2.ZERO, target: Node = null) -> void:
	var event := InputEventMouseButton.new()
	event.button_index = button
	event.pressed = true
	event.position = position
	event.global_position = position
	send_event(event, target)
	if not _pressed_buttons.has(button):
		_pressed_buttons.append(button)


## Release a mouse button.
func mouse_up(button: int = MOUSE_BUTTON_LEFT, position: Vector2 = Vector2.ZERO, target: Node = null) -> void:
	var event := InputEventMouseButton.new()
	event.button_index = button
	event.pressed = false
	event.position = position
	event.global_position = position
	send_event(event, target)
	_pressed_buttons.erase(button)


## Move the mouse pointer.
func mouse_move(
	position: Vector2, relative: Vector2 = Vector2.ZERO, target: Node = null
) -> void:
	var event := InputEventMouseMotion.new()
	event.position = position
	event.global_position = position
	event.relative = relative
	send_event(event, target)


## Press and release a mouse button in one call.
func click(
	position: Vector2 = Vector2.ZERO, button: int = MOUSE_BUTTON_LEFT, target: Node = null
) -> void:
	mouse_down(button, position, target)
	mouse_up(button, position, target)


## Release every action, key, and mouse button this test pressed.
func reset_inputs() -> void:
	for action in _pressed_actions.duplicate():
		action_up(action)
	for keycode in _pressed_keys.duplicate():
		key_up(keycode)
	for button in _pressed_buttons.duplicate():
		mouse_up(button)


# Watch signals.

## Record emissions of [param signal_name] on [param object].
func watch_signal(object: Object, signal_name: StringName) -> void:
	if object == null:
		fail("watch_signal: object is null")
		return
	var key := _signal_key(object, signal_name)
	if _signal_counts.has(key):
		return
	var argument_count := _signal_arg_count(object, signal_name)
	if argument_count < 0:
		fail("watch_signal: %s has no signal %s" % [object, signal_name])
		return
	if argument_count > MAX_SIGNAL_ARGS:
		fail(
			"watch_signal: %s.%s has %d arguments; the limit is %d"
			% [object, signal_name, argument_count, MAX_SIGNAL_ARGS]
		)
		return
	var callback := _signal_handler(argument_count).bind(object, signal_name)
	var error := object.connect(signal_name, callback)
	if error != OK:
		fail("watch_signal: cannot connect %s.%s (error %d)" % [object, signal_name, error])
		return
	_signal_counts[key] = 0
	_watchers.append({"object": object, "signal": signal_name, "callable": callback})


## Watch every signal of [param object] that has 6 arguments or fewer.
func watch_signals(object: Object) -> void:
	if object == null:
		fail("watch_signals: object is null")
		return
	for info in object.get_signal_list():
		if (info["args"] as Array).size() <= MAX_SIGNAL_ARGS:
			watch_signal(object, StringName(info["name"]))


func signal_count(object: Object, signal_name: StringName) -> int:
	if object == null or not is_instance_valid(object):
		return 0
	return int(_signal_counts.get(_signal_key(object, signal_name), 0))


func assert_signal_emitted(object: Object, signal_name: StringName, message: String = "") -> bool:
	if not _watched(object, signal_name):
		return _fail("signal %s is not watched; call watch_signal first%s" % [signal_name, _suffix(message)])
	if signal_count(object, signal_name) > 0:
		return true
	return _fail("signal %s was not emitted%s" % [signal_name, _suffix(message)])


func assert_signal_not_emitted(object: Object, signal_name: StringName, message: String = "") -> bool:
	if not _watched(object, signal_name):
		return _fail("signal %s is not watched; call watch_signal first%s" % [signal_name, _suffix(message)])
	if signal_count(object, signal_name) == 0:
		return true
	return _fail(
		"signal %s was emitted %d times%s"
		% [signal_name, signal_count(object, signal_name), _suffix(message)]
	)


func assert_signal_emit_count(
	object: Object, signal_name: StringName, expected: int, message: String = ""
) -> bool:
	if not _watched(object, signal_name):
		return _fail("signal %s is not watched; call watch_signal first%s" % [signal_name, _suffix(message)])
	var count := signal_count(object, signal_name)
	if count == expected:
		return true
	return _fail(
		"signal %s was emitted %d times, expected %d%s"
		% [signal_name, count, expected, _suffix(message)]
	)


# Assertions.

func assert_true(value: Variant, message: String = "") -> bool:
	if bool(value):
		return true
	return _fail("expected true, got %s%s" % [_show(value), _suffix(message)])


func assert_false(value: Variant, message: String = "") -> bool:
	if not bool(value):
		return true
	return _fail("expected false, got %s%s" % [_show(value), _suffix(message)])


func assert_eq(got: Variant, expected: Variant, message: String = "") -> bool:
	if got == expected:
		return true
	return _fail("expected %s, got %s%s" % [_show(expected), _show(got), _suffix(message)])


func assert_ne(got: Variant, unexpected: Variant, message: String = "") -> bool:
	if got != unexpected:
		return true
	return _fail("expected a value other than %s%s" % [_show(unexpected), _suffix(message)])


func assert_almost_eq(
	got: float, expected: float, tolerance: float = 0.00001, message: String = ""
) -> bool:
	if absf(got - expected) <= tolerance:
		return true
	return _fail(
		"expected %s +/- %s, got %s%s"
		% [_show(expected), _show(tolerance), _show(got), _suffix(message)]
	)


func assert_null(value: Variant, message: String = "") -> bool:
	if value == null:
		return true
	return _fail("expected null, got %s%s" % [_show(value), _suffix(message)])


func assert_not_null(value: Variant, message: String = "") -> bool:
	if value != null:
		return true
	return _fail("expected a value, got null%s" % [_suffix(message)])


func assert_has(container: Variant, value: Variant, message: String = "") -> bool:
	if container == null:
		return _fail("expected a container, got null%s" % [_suffix(message)])
	if value in container:
		return true
	return _fail("expected %s in %s%s" % [_show(value), _show(container), _suffix(message)])


func assert_size(container: Variant, expected: int, message: String = "") -> bool:
	if container == null:
		return _fail("expected a container, got null%s" % [_suffix(message)])
	var size: int = container.size()
	if size == expected:
		return true
	return _fail("expected size %d, got %d%s" % [expected, size, _suffix(message)])


# The runner calls these.

func _gai_reset() -> void:
	_disconnect_watchers()
	for node in _auto_free_nodes:
		if is_instance_valid(node):
			if node.get_parent() != null:
				node.get_parent().remove_child(node)
			node.free()
	_auto_free_nodes.clear()
	reset_inputs()
	_double_calls.clear()
	_double_stubs.clear()
	failures.clear()
	pending_reason = ""
	_signal_counts.clear()


## Runs before each test. Override it; it can await.
func before_each() -> void:
	pass


## Runs after each test. Override it; it can await.
func after_each() -> void:
	pass


func _fail(message: String) -> bool:
	failures.append(message)
	return false


func _watched(object: Object, signal_name: StringName) -> bool:
	if object == null or not is_instance_valid(object):
		return false
	return _signal_counts.has(_signal_key(object, signal_name))


func _signal_key(object: Object, signal_name: StringName) -> String:
	return "%d:%s" % [object.get_instance_id(), signal_name]


func _signal_arg_count(object: Object, signal_name: StringName) -> int:
	for info in object.get_signal_list():
		if StringName(info["name"]) == signal_name:
			return (info["args"] as Array).size()
	return -1


func _signal_handler(argument_count: int) -> Callable:
	match argument_count:
		0:
			return Callable(self, "_on_signal_0")
		1:
			return Callable(self, "_on_signal_1")
		2:
			return Callable(self, "_on_signal_2")
		3:
			return Callable(self, "_on_signal_3")
		4:
			return Callable(self, "_on_signal_4")
		5:
			return Callable(self, "_on_signal_5")
		6:
			return Callable(self, "_on_signal_6")
	return Callable()


func _on_signal_0(object: Object, signal_name: StringName) -> void:
	_record_signal(object, signal_name)


func _on_signal_1(_a: Variant, object: Object, signal_name: StringName) -> void:
	_record_signal(object, signal_name)


func _on_signal_2(
	_a: Variant, _b: Variant, object: Object, signal_name: StringName
) -> void:
	_record_signal(object, signal_name)


func _on_signal_3(
	_a: Variant, _b: Variant, _c: Variant, object: Object, signal_name: StringName
) -> void:
	_record_signal(object, signal_name)


func _on_signal_4(
	_a: Variant,
	_b: Variant,
	_c: Variant,
	_d: Variant,
	object: Object,
	signal_name: StringName
) -> void:
	_record_signal(object, signal_name)


func _on_signal_5(
	_a: Variant,
	_b: Variant,
	_c: Variant,
	_d: Variant,
	_e: Variant,
	object: Object,
	signal_name: StringName
) -> void:
	_record_signal(object, signal_name)


func _on_signal_6(
	_a: Variant,
	_b: Variant,
	_c: Variant,
	_d: Variant,
	_e: Variant,
	_f: Variant,
	object: Object,
	signal_name: StringName
) -> void:
	_record_signal(object, signal_name)


func _record_signal(object: Object, signal_name: StringName) -> void:
	var key := _signal_key(object, signal_name)
	_signal_counts[key] = int(_signal_counts.get(key, 0)) + 1


func _disconnect_watchers() -> void:
	for watcher in _watchers:
		var object: Object = watcher["object"]
		var signal_name: StringName = watcher["signal"]
		var callback: Callable = watcher["callable"]
		if is_instance_valid(object) and object.is_connected(signal_name, callback):
			object.disconnect(signal_name, callback)
	_watchers.clear()


func _suffix(message: String) -> String:
	return "" if message.is_empty() else " (" + message + ")"


func _show(value: Variant) -> String:
	var text := var_to_str(value)
	if text.length() > 200:
		text = text.substr(0, 197) + "..."
	return text
