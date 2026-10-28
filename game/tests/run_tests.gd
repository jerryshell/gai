extends SceneTree
## Headless test runner for gai games.
##
## Run it through the CLI:
##
## [codeblock]
## bin/gai test
## bin/gai test --filter player
## bin/gai test --json
## [/codeblock]
##
## The runner discovers [code]test_*.gd[/code] files under [code]res://tests[/code]
## (or [code]--dir[/code]), runs every [code]test_*[/code] method, prints one
## [code]GAI_TEST_RESULT[/code] JSON line, and exits with 1 when a test fails.

var _test_dir: String = "res://tests"
var _filter: String = ""
var _json_only: bool = false
var _only_file: String = ""
var _only_method: String = ""
var _list_only: bool = false


func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--dir="):
			_test_dir = argument.trim_prefix("--dir=")
		elif argument.begins_with("--filter="):
			_filter = argument.trim_prefix("--filter=")
		elif argument == "--json":
			_json_only = true
		elif argument.begins_with("--file="):
			_only_file = argument.trim_prefix("--file=")
		elif argument.begins_with("--method="):
			_only_method = argument.trim_prefix("--method=")
		elif argument == "--list":
			_list_only = true
	_run.call_deferred()


func _run() -> void:
	var started := Time.get_ticks_msec()
	if not _test_dir.begins_with("res://"):
		print("test: --dir must start with res://")
		quit(2)
		return

	var files: Array[String] = []
	if not _only_file.is_empty():
		if not _only_file.begins_with("res://"):
			print("test: --file must start with res://")
			quit(2)
			return
		files.append(_only_file)
	else:
		_collect(_test_dir, files)
		files.sort()

	var results: Array[Dictionary] = []
	var passed := 0
	var failed := 0
	var pending := 0
	var skipped := 0

	if _list_only:
		var listed: Array = []
		for file in files:
			var script := load(file) as GDScript
			if script == null:
				continue
			for method in _test_methods(script):
				if not _only_method.is_empty() and method != _only_method:
					continue
				if _matches(file, method):
					listed.append({"file": file, "name": method})
		print("GAI_TEST_LIST " + JSON.stringify(listed))
		quit(0)
		return

	for file in files:
		var script := load(file) as GDScript
		if script == null or not script.can_instantiate():
			var load_failure := {
				"file": file,
				"name": "<load>",
				"status": "fail",
				"failures": ["cannot load or instantiate the test script (parse error or required _init arguments?)"],
				"pending": "",
				"duration_ms": 0,
			}
			results.append(load_failure)
			failed += 1
			_emit(load_failure)
			continue

		var methods := _test_methods(script)
		if methods.is_empty():
			skipped += 1
			if not _json_only:
				print("SKIP %s (no test_ methods)" % file)
			continue

		var instance: Object = script.new()
		if instance == null or not instance.has_method("_gai_test_case"):
			var base_failure := {
				"file": file,
				"name": "<base>",
				"status": "fail",
				"failures": [
					"test scripts must extend res://tests/gai_test_case.gd"
				],
				"pending": "",
				"duration_ms": 0,
			}
			results.append(base_failure)
			failed += 1
			_emit(base_failure)
			continue

		for method in methods:
			if not _only_method.is_empty() and method != _only_method:
				continue
			if not _matches(file, method):
				continue
			var result: Dictionary = await _run_one(instance, file, method)
			results.append(result)
			match String(result["status"]):
				"pass":
					passed += 1
				"fail":
					failed += 1
				"pending":
					pending += 1
			_emit(result)

		instance.call("_gai_reset")

	var summary := {
		"version": 1,
		"dir": _test_dir,
		"filter": _filter,
		"files": files.size(),
		"skipped_files": skipped,
		"tests": results.size(),
		"passed": passed,
		"failed": failed,
		"pending": pending,
		"duration_ms": Time.get_ticks_msec() - started,
		"results": results,
	}

	if not _json_only:
		print("")
		if results.is_empty():
			if _filter.is_empty():
				print("tests: no tests in %s" % _test_dir)
			else:
				print("tests: no tests matched `%s` in %s" % [_filter, _test_dir])
		else:
			print(
				"tests: %d passed, %d failed, %d pending (%d ms)"
				% [passed, failed, pending, summary["duration_ms"]]
			)

	print("GAI_TEST_RESULT " + JSON.stringify(summary))
	var exit_code := 0
	if failed > 0:
		exit_code = 1
	elif not _filter.is_empty() and results.is_empty():
		exit_code = 1
	quit(exit_code)


func _run_one(instance: Object, file: String, method: String) -> Dictionary:
	var started := Time.get_ticks_msec()
	instance.call("_gai_reset")
	await instance.call("before_each")
	var setup_failed: bool = not (instance.get_failures() as Array).is_empty()
	if not setup_failed:
		await instance.call(method)
	await instance.call("after_each")
	var failures: Array = (instance.get_failures() as Array).duplicate()
	var pending_text := String(instance.get_pending_reason())
	var status := "pass"
	if not failures.is_empty():
		status = "fail"
	elif not pending_text.is_empty():
		status = "pending"
	return {
		"file": file,
		"name": method,
		"status": status,
		"failures": failures,
		"pending": pending_text,
		"duration_ms": Time.get_ticks_msec() - started,
	}


func _emit(result: Dictionary) -> void:
	if _json_only:
		return
	var status := String(result["status"]).to_upper()
	print(
		"%s %s::%s (%d ms)"
		% [status, result["file"], result["name"], result["duration_ms"]]
	)
	if status == "FAIL":
		for failure in result["failures"]:
			print("  " + String(failure))
	elif status == "PENDING":
		print("  " + String(result["pending"]))


func _collect(path: String, out: Array[String]) -> void:
	var directory := DirAccess.open(path)
	if directory == null:
		return
	directory.list_dir_begin()
	var name := directory.get_next()
	while name != "":
		if not name.begins_with("."):
			var full := path.path_join(name)
			if directory.current_is_dir():
				_collect(full, out)
			elif name.ends_with(".gd") and name.begins_with("test_"):
				out.append(full)
		name = directory.get_next()
	directory.list_dir_end()


func _test_methods(script: GDScript) -> Array[String]:
	var methods: Array[String] = []
	for method in script.get_script_method_list():
		var name: String = method["name"]
		if name.begins_with("test_") and not methods.has(name):
			methods.append(name)
	methods.sort()
	return methods


func _matches(file: String, method: String) -> bool:
	if _filter.is_empty():
		return true
	return (file + "::" + method).to_lower().contains(_filter.to_lower())
