extends RefCounted

var damage: int = 0


func take_damage(amount: int = 1) -> int:
	damage += amount
	return amount


func heal(amount: int) -> void:
	damage -= amount


func is_alive() -> bool:
	return damage < 3


func set_position(value: Vector2 = Vector2.ZERO) -> Vector2:
	return value


func label(text: String = "x") -> String:
	return text


func target(node: Node = null) -> bool:
	return node != null


func list(values: Array = []) -> Array:
	return values


func dict(options: Dictionary = {}) -> Dictionary:
	return options
