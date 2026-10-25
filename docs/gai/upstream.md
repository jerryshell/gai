# Merge an upstream release

Use this when Godot publishes a new tag, for example `4.8-stable`.

## Before you start

- You are on `main` with no uncommitted changes to tracked files.
- `bin/gai check` passes.
- You can reach github.com.

## Merge

```sh
bin/gai upstream merge 4.8-stable
```

The command adds the `upstream` remote when it is missing, fetches tags, runs
`git merge --no-commit --no-ff`, checks the result against the new base, records
the base in `.gai/upstream.json`, and commits.

If `version.py` conflicts, the command resolves it. It takes upstream's file
and re-applies our `name` and `website`. The new version numbers and `docs`
value stay.

If it stops with other conflicts, resolve only the listed files.

| File | Policy |
| --- | --- |
| `README.md` | Keep ours. Then add any upstream fact the front door needs. |
| `version.py` | The tool resolves it. Resolve it by hand only if the automatic step failed. |
| `.gitignore` | Keep both sets of rules. |

Then:

```sh
git add <files>
bin/gai upstream continue
```

If the automatic `version.py` step fails, take upstream's file and set
`name = "gai"` and our website by hand.

To back out:

```sh
bin/gai upstream abort
```

## After the merge

```sh
bin/gai engine install --force
bin/gai check
python3 tests/test_upstream.py
```

Run the test suite. If Godot changes the release asset names, update `RELEASES`
in `bin/gai`.

Update the version strings that describe the project:

```sh
grep -rn '4\.7' README.md AGENTS.md docs/gai .agents game/project.godot
```

Replace the engine version, the `config/features` value, and the doc headings.
The editor rewrites `game/project.godot` when it saves the project. Commit that
change.

Commit any doc updates.

If you build the engine from source, rebuild it. `bin/gai` prefers a source build
under `bin/godot.*.editor.*` over the downloaded binary.

## What not to do

- Do not rebase `main`. People clone it.
- Do not edit an upstream file outside the allowlist. Put gai code in an owned
  path.
- Do not move the base by hand. The merge command owns `.gai/upstream.json`.
- Do not merge with a dirty working tree.

## Check the invariant

```sh
bin/gai upstream check
```

The command fails on a path outside `.gai/upstream.json`. CI runs it with full
history.
