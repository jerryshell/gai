# gai

Godot, but AI Native.

gai is a fork of Godot 4.7.2 that you clone as your game. The engine source is
here, a starter game is in `game/`, and pi or opencode can work on it from the
first minute.

## Start

```sh
git clone git@github.com:jerryshell/gai.git my-game
cd my-game
bin/gai engine install
bin/gai check
bin/gai editor
```

Then open `my-game` in pi or opencode and describe the game you want. The agent
reads `AGENTS.md` and works in `game/`.

`bin/gai engine install` downloads the official Godot 4.7.2 binary (about 140 MB)
and checks its SHA-512. The clone carries the full Godot history, about 1.2 GB in
`.git`. That history is what makes upstream merges cheap.

On Windows, run `python bin/gai` in place of `bin/gai`.

## What an agent gets

- `AGENTS.md` holds the workflow, the commands, and the Godot rules that agents
  get wrong.
- `.agents/skills/godot-game/` holds scene formats, GDScript patterns, and an
  error catalog. Pi and other Agent Skills tools load it when a task needs it.
- `bin/gai check` imports assets, parses every script, runs the main scene, and
  fails on errors. Godot exits 0 on a script error. This command does not.
- `game/` holds a small 2D scene that runs. Replace it.

## What is here

| Path | What it is |
| --- | --- |
| `game/` | Your Godot project. |
| engine source | Godot 4.7.2-stable, unchanged except the display name and project URL. |
| `.gai/` | gai metadata: version, upstream base, layer rules. |
| `bin/gai` | The command line. Python 3, no dependencies. |
| `docs/gai/` | Architecture, upstream sync, build, and decisions. |

## Stay close to upstream

The engine tracks `godotengine/godot`. The base is recorded in
`.gai/upstream.json`. To move to a new release:

```sh
bin/gai upstream merge 4.8-stable
bin/gai engine install --force
bin/gai check
```

Conflicts can appear only in the files the layer edits: `README.md`,
`version.py`, and `.gitignore`. The tool prints the policy for each.
`bin/gai upstream check` fails when a commit changes any other upstream file, so
the layer cannot grow by accident.

Read `docs/gai/upstream.md` before you sync.

## Status

Version 0.1.0. The display name is gai. Internal identifiers and the binary name
stay `godot` so upstream merges stay cheap. The editor icon, splash, and UI
strings are still Godot. There is no in-editor AI panel.

gai is not affiliated with the Godot Foundation. See `NOTICE.md`.

## License

MIT, like Godot. See `LICENSE.txt`.
