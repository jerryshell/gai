extends "res://tests/gai_test_case.gd"
## Tests for doubles, spies, and stubs. Replace them with tests for your game.


func test_double_spy_stub() -> void:
	var combat = double("res://tests/fixtures/combat.gd")
	assert_not_null(combat, "double is created")
	if combat == null:
		return
	assert_eq(combat.take_damage(2), 2)
	assert_called(combat, "take_damage", [2])
	assert_call_count(combat, "take_damage", 1)
	assert_not_called(combat, "heal")

	stub(combat, "take_damage", 99, [5])
	assert_eq(combat.take_damage(5), 99)
	assert_eq(combat.take_damage(4), 4)
	assert_call_count(combat, "take_damage", 3)

	combat.heal(1)
	assert_called(combat, "heal", [1])


func test_double_selective() -> void:
	var script := double_script("res://tests/fixtures/combat.gd", ["heal"])
	assert_not_null(script)
	if script == null:
		return
	var combat = script.new()
	combat.__gai_test = self
	combat.heal(2)
	assert_called(combat, "heal", [2])
	combat.take_damage(1)
	assert_not_called(combat, "take_damage")


func test_double_wildcard_stub() -> void:
	var combat = double("res://tests/fixtures/combat.gd")
	assert_not_null(combat)
	if combat == null:
		return
	stub(combat, "take_damage", 7)
	assert_eq(combat.take_damage(1), 7)
	assert_eq(combat.take_damage(9), 7)
	assert_call_count(combat, "take_damage", 2)


func test_double_defaults() -> void:
	var combat = double("res://tests/fixtures/combat.gd")
	assert_not_null(combat)
	if combat == null:
		return
	assert_eq(combat.set_position(Vector2(1, 2)), Vector2(1, 2))
	assert_eq(combat.label(), "x")
	assert_false(combat.target())
	stub(combat, "label", "stubbed")
	assert_eq(combat.label(), "stubbed")


func test_double_node() -> void:
	var actor := double("res://tests/fixtures/actor.gd") as Node
	assert_not_null(actor)
	if actor == null:
		return
	auto_free(actor)
	actor.ping()
	assert_called(actor, "ping")
	assert_eq(actor.pings, 1)


func test_double_collection_defaults() -> void:
	var combat = double("res://tests/fixtures/combat.gd")
	assert_not_null(combat)
	if combat == null:
		return
	assert_eq(combat.list([1, 2]), [1, 2])
	assert_called(combat, "list", [[1, 2]])
	assert_eq(combat.dict(), {})
	assert_called(combat, "dict", [{}])
