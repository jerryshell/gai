# Game tests

`bin/gai check` proves that assets import, scripts parse, and the main scene
runs. It does not prove that the game behaves correctly. `bin/gai test` runs
`game/tests` headlessly and fails when an assertion fails.

## Run

| Command | What it does |
| --- | --- |
| `bin/gai test` | Run every `test_*` method in `game/tests/test_*.gd`. |
| `bin/gai test --filter player` | Run tests whose `file::name` contains `player`. A filter with no match exits 1. |
| `bin/gai test --json` | Print one JSON object. |
| `bin/gai test --verbose` | Print the engine output. |
| `bin/gai check` | Run the game checks and the tests. |
| `bin/gai check --no-tests` | Skip the tests. |

`check` runs the tests only when `game/tests/run_tests.gd` exists. Delete the
runner to opt a project out, or pass `--no-tests`. `check` always reads
`res://tests`; `--dir` changes the directory for `bin/gai test` only.

## Layout

```text
game/tests/
  gai_test_case.gd   base class; keep it
  run_tests.gd       runner; keep it
  test_main.gd       your tests
  fixtures/          optional scripts used only by tests
```

## Write a test

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

- Each method named `test_*` runs once. Tests run in name order.
- Use the base class assertions, not GDScript's `assert()`. The built-in `assert()`
  aborts the method and prints an engine error. `bin/gai test` reports the error,
  but the test result itself cannot see the assertion.
- `before_each()` and `after_each()` run around each test. Both can await.
- An assertion records a failure and returns false. The test continues after a
  failed assertion, so `return` when a later step needs the value.
- `auto_free(node)` adds the node to the tree and frees it after the test.
- `await frames(n)` and `await physics_frames(n)` wait for process or physics
  frames. `await seconds(s)` waits for wall-clock time.
- `await wait_until(callable, timeout)` waits for a condition. It returns false
  after the timeout, so assert on the result.
- `pending("reason")` marks a test pending. Call `return` after it.
- Do not override a method that starts with `_gai_`. They are the runner's.
- A test instance is a `RefCounted`. Use `tree()` to reach the `SceneTree`, not
  `get_tree()`.
- The project autoloads are loaded.

## Assertions

`assert_true`, `assert_false`, `assert_eq`, `assert_ne`, `assert_almost_eq`,
`assert_null`, `assert_not_null`, `assert_has`, `assert_size`,
`assert_signal_emitted`, `assert_signal_not_emitted`, and
`assert_signal_emit_count`.

Every assertion takes an optional message as its last argument. `assert_eq` is
exact; use `assert_almost_eq` for floats.

## Signals

`watch_signal(object, &"signal_name")` records emissions. `watch_signals(object)`
watches every signal with 6 arguments or fewer. Watch before the event:

```gdscript
var timer := auto_free(Timer.new())
watch_signal(timer, &"timeout")
timer.start(0.01)
await seconds(0.02)
assert_signal_emit_count(timer, &"timeout", 1)
```

A signal with more than 6 arguments cannot be watched. Errors raised inside the
watched object's own signal handler are not caught.

## Input

Press and release actions, keys, and mouse buttons. The helpers send a real
event and update `Input` state. `_gai_reset` releases anything a test left down.

```gdscript
func test_jump() -> void:
	action_down(&"jump")
	await frames(2)
	assert_true(Input.is_action_pressed(&"jump"))
	action_up(&"jump")
	await frames(1)
	assert_false(Input.is_action_pressed(&"jump"))
```

- `action_down`, `action_up`, and `action_press`.
- `key_down` and `key_up`.
- `mouse_down`, `mouse_up`, `mouse_move`, and `click`.
- `send_event(event, target)` sends to a `Control`, `Viewport`, or `Node`
  instead of the global input state.
- Declare the action in `project.godot` first.
- Use `action_down`, wait, then `action_up` when the game checks
  `Input.is_action_just_pressed`. `action_press` sends both events in one frame.

## Doubles, spies, and stubs

`double("res://player.gd")` returns an instance of a generated subclass. The
subclass calls the real method and records the call.

```gdscript
func test_damage() -> void:
	var player = double("res://player.gd")
	assert_eq(player.take_damage(2), 2)
	assert_called(player, "take_damage", [2])
	stub(player, "take_damage", 99, [5])
	assert_eq(player.take_damage(5), 99)
```

- `double(path, methods)` creates the instance. A `Node` double must be passed
  to `auto_free`:

  ```gdscript
  var actor := double("res://actor.gd") as Node
  auto_free(actor)
  ```

  A `RefCounted` double lives as long as your variable.
- `double_script(path, methods)` returns the generated script. Set
  `instance.__gai_test = self` before you use it.
- `stub(object, method, value, args)` returns `value` for one argument list, or
  for every call when `args` is null. The list is what the method receives,
  including defaults.
- `assert_called`, `assert_not_called`, `assert_call_count`, and `get_calls`
  inspect the recorded calls. A call records the actual arguments, including
  defaults that the caller omitted.
- Only GDScript scripts with a path work. Only methods declared in that script
  are overridden; inherited methods are not. Methods that start with `_`, or
  that are static, virtual, vararg, or have a non-literal default, are skipped.
  Pass `methods` to choose; `double_script` records a failure when a requested
  method cannot be overridden.
- Annotations such as `@rpc` are not copied to the override. Do not double a
  method whose annotation changes engine behavior.
- A plain object cannot be spied. Double its script and use the instance.

## What the runner does

- Discovers `test_*.gd` under `res://tests` (or `--dir`), recursively.
- Runs in one engine process with the project autoloads.
- Prints `PASS`, `FAIL`, or `PENDING` for each test, then a summary.
- Prints one `GAI_TEST_RESULT {...}` JSON line. The fields are `tests`,
  `passed`, `failed`, `pending`, `duration_ms`, and `results`. Each result has
  `file`, `name`, `status`, `failures`, `pending`, and `duration_ms`.
- Exits 0 when every test passes or is pending; 1 when a test fails.

`bin/gai test` also fails when the engine prints an `ERROR:` or `SCRIPT ERROR:`
line, even when the test method returned. A runtime error aborts that method,
so the runner cannot mark it failed by itself. Do not print engine errors from a
test that should pass.

## Limits

- Tests run in one engine process. A blocking loop hangs the run until the CLI
  timeout. `bin/gai test` defaults to 300 seconds; `bin/gai check` uses its own
  per-step `--timeout` (default 120 seconds).
- A test that calls `quit()` stops the runner.
- Doubles cover eligible GDScript methods only. There is no scene doubling;
  instantiate a scene yourself when the test needs its child nodes.
- Tests are development-time code. Exclude `tests/` from an export preset when
  the build must not ship test scripts.
- This runner is gai's own; it is not GUT. The base class and the assertion
  names are GUT-like. Blazium's Autowork is the engine-level reference (native
  `ClassDB` assertions, E2E server) if gai needs more.

## Version

The result JSON has `"version": 1`. A change to the fields must raise it.
