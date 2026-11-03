# 0006 Script reflection reads res:// when the cache is empty

Date: 2026-11-03
Status: accepted

## Context

`classdb.*` reflects the engine. A GDScript `class_name` is not in `ClassDB`, so
an agent had two options: find a live instance and read its script through a
handle, or read the `.gd` file and parse it. Both cost round trips, and the
second one makes the agent's idea of a script diverge from the engine's.

The engine already knows the answer, in `.godot/global_script_class_cache.cfg`.
`ProjectSettings::get_global_class_list()` reads it.

The cache is written by the editor's file system scan. A game run does not write
it. Measured on this repository: a fresh copy of `game/` with a `class_name`
script, started as `godot --headless --path . --quit-after 2`, creates no
`.godot` directory at all, and `get_global_class_list()` returns an empty list.
That is the first-run state of every gai project, and it is also the state
`bin/gai agent start` runs in.

## Decision

One index, built from two sources, in this order:

1. `ProjectSettings::get_global_class_list()`, tagged `source: import cache`.
2. A bounded `res://` scan for `class_name` and `extends` lines, tagged
   `source: res:// scan`. The scan stops after 2000 `.gd` files and skips
   folders whose name starts with a dot.

A class name found twice keeps the import cache entry, because the engine's own
registration wins. `script.class` resolves a class to a path through the same
index, then loads the script with `ResourceLoader` and reads properties,
signals, methods, constants, and doc from the engine.

## Why scan at all

- The scan needs no import pass, no editor, and no cache file. A project that
  has never been opened answers on the first call.
- The alternative, an error that says "import the project first", moves a
  mechanical step onto the agent and is wrong on the exact path gai promises:
  clone, describe a game, run one command.
- 2000 files bounds the worst case. A project that large has other problems
  before this one.

## Consequences

- The index is per-process and cached. `script.classes` with
  `{"refresh": true}` rebuilds it, and the loaded scripts go with it.
- Two sources can disagree after an editor session changes a `class_name` and
  the game runs without a reimport. The import cache entry wins; `refresh`
  reports what the files say.
- Properties, methods, and signals always come from the loaded script, so they
  are the engine's answer even when the index came from the scan.
- `doc` is present only when the build parses docs, which is an editor build.
  A non-editor build returns no `doc` key, and the documentation does not claim
  otherwise.

## Revisit

Revisit if the engine gains a runtime class registration path, or if the scan
cost shows up in a large project.

## Addendum 2026-11-03

The first version loaded a script with the default cache mode. A test edited a
script, called `refresh`, and still read the old export default. Both reuse and
replace route to `GDScriptCache`, so a reload must pass `CACHE_MODE_IGNORE`. A
script then parses again on change, not on every call, and the bridge keeps the
`Ref<Script>` for a file whose modification time did not move.
