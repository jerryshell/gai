# Error catalog

Read `.gai/logs/check.log`. Fix the first error, then run `bin/gai check` again.

| Message | Cause | Fix |
| --- | --- | --- |
| `SCRIPT ERROR: Parse Error: ...` | GDScript syntax, or mixed tabs and spaces | Use tabs, close the expression. |
| `Failed to load script "res://..."` | Wrong path, or the script does not parse | Fix the path. Open the file and parse error above it. |
| `Node not found: "X" (relative to "/root/Main")` | `$X` does not exist at that point | Check the scene tree. Wait for `_ready`. Use `%X` only with `unique_name_in_owner`. |
| `Invalid call. Nonexistent function 'x' in base 'y'` | Wrong method name or wrong node type | Check the method in the Godot docs and the node type. |
| `Invalid get index 'x' (on base: 'Nil')` | A node or value is null | Check `@onready`, `add_child` order, and the path. |
| `Invalid assignment of property or key 'x' ... on a base object of type 'null instance'` | The target node is null | Same as above. |
| `Cannot open file "res://..."` | The file is missing or the path is wrong | Create the file or fix the path. Use `res://`. |
| `Failed to load resource "res://..."` | Broken `.tscn`, `.tres`, or missing dependency | Open the file, fix the reference, run the check. |
| `Condition "!is_inside_tree()" is true` | A node method ran before the node entered the tree | Move the call to `_ready`, or use `call_deferred`. |
| `E 0:00:00:...` with a script path | A runtime error with its location | Open the file at that line. |

`WARNING:` lines do not fail `bin/gai check`. Fix them when they point at your
code.
