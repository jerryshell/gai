# Architecture

gai has three layers. Each layer has one owner.

| Layer | Files | Owner |
| --- | --- | --- |
| Upstream Godot | every file from the 4.7.2-stable tag | The Godot project |
| gai layer | new files, plus three edited upstream files | This repository |
| Your game | `game/` | You and your agent |

## The invariant

`main` is upstream Godot plus a thin layer. `.gai/upstream.json` records the
upstream commit we last merged, and the paths that are allowed to differ:

- `owned_prefixes` are directories that contain only gai files: `.gai/`,
  `.agents/`, `docs/gai/`, and `game/`.
- `owned_files` are individual new files, such as `bin/gai`, `AGENTS.md`,
  `NOTICE.md`, and the CI workflow.
- `edited` lists the upstream files we change: `README.md`, `version.py`, and
  `.gitignore`.
- `required` lists core layer files that must exist in every commit.

`bin/gai upstream check` diffs the recorded base against `HEAD`. Every path must
be owned or edited. Anything else fails. CI runs the check on every push.

## Why merge, not rebase

| Option | Effect on a 4.8 update |
| --- | --- |
| Merge tags into `main` | One merge commit. Conflicts stay inside the allowlist. Clones stay valid. |
| Rebase onto the new tag | Rewrites public history. Every clone must reset. Conflicts remain. |
| Rebrand the whole source | Hundreds of files change. Every release conflicts. |
| Vendor the engine into the game | Loses upstream history and the ability to merge. |

The merge wins because the rule that keeps it cheap is structural. Put gai code
in new paths, and edit as few upstream files as possible. See
`decisions/0001-thin-layer.md`.

## The branding line

`version.py` sets the display name:

```python
short_name = "godot"
name = "gai"
website = "https://github.com/jerryshell/gai"
```

`short_name` stays `godot`. `methods.py` checks for that exact string when it
detects the engine source, and `platform/linuxbsd/SCsub` hardcodes `#bin/godot`
as the build target. Changing either would push the brand into the build system
and create conflicts for no user-visible gain. The window title, version header,
and crash reports use the new display name.

Full UI rebranding is out of scope for 0.1.0.

## What check proves

Godot 4.7.2 exits 0 when a scene hits a parse or runtime error. The engine prints
`SCRIPT ERROR` and returns success. A CI job that checks only the exit code
passes a broken game.

`bin/gai check` runs three stages and fails on any `ERROR`, `SCRIPT ERROR`, or
`SHADER ERROR` line:

1. `--import` loads the project and imports assets.
2. `--check-only --script` parses every `.gd` file under `game/`.
3. `--quit-after 5` runs the main scene and catches runtime errors.

Before the stages, `check` compares the engine and `version.py` to the recorded
upstream tag. It refuses to run on a mismatched engine, so a forgotten
`engine install --force` cannot leave a green check on the old version.

The full output goes to `.gai/logs/check.log`.

## The agent surface

Agents already have a shell. `bin/gai` is one Python file with no dependencies,
so it works in pi, opencode, a terminal, or CI. The instructions are in
`AGENTS.md`. The detailed Godot patterns are in
`.agents/skills/godot-game/`, which Pi and other Agent Skills tools load on
demand.

There is no MCP server and no editor plugin in 0.1.0. Both add a process or
engine code to maintain. See `decisions/0002-cli-first.md`.

## Limits

- The game lives in `game/`. The repository root is not a Godot project, so do
  not point the editor at it.
- A shallow clone cannot run `upstream check`, because the recorded base commit
  is missing. CI checks out full history for this job.
- The skill and docs describe 4.7.2. Update them when a merge changes behavior.
- `upstream merge` follows one release line. After 4.8, an older 4.7 maintenance
  tag is already in history and the tool will not merge it back.
