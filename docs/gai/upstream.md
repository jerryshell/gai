# Merge an upstream release

Use this when Godot publishes a new tag, for example `4.8-stable`.

## Before you start

- You are on `main` with no uncommitted changes to tracked files.
- The engine builds and the feature tests pass.
- `bin/gai upstream report` shows the current features and divergence.
- You can reach github.com.

## Merge

```sh
bin/gai upstream merge 4.8-stable
```

The command adds the `upstream` remote when it is missing, fetches tags, runs
`git merge --no-commit --no-ff`, checks that every changed engine path has an
active feature, records the base in `.gai/upstream.json`, and commits.

If `version.py` conflicts, the command resolves it as part of the `branding`
feature. It takes upstream's file and re-applies our `name` and `website`. The
new version numbers and `docs` value stay.

## Resolve conflicts

Deep fork conflicts are expected. The merge command lists each conflict with its
owner:

```text
merge conflicts:
  README.md (workspace)
  platform/web/export/export_plugin.cpp (unclaimed)
```

- The feature owner resolves its files. Read the feature doc and keep the
  feature behavior.
- Workspace conflicts, such as `README.md` and docs, are resolved by whoever owns
  the workspace.
- An unclaimed conflict is a missing feature manifest. Add one, or activate the
  feature that should own the file, before you resolve it.

Then:

```sh
git add <files>
bin/gai upstream continue
```

To back out:

```sh
bin/gai upstream abort
```

## After the merge

1. Build the engine. See `docs/gai/build.md`.
2. Run the feature tests.
3. Run the game gate:

```sh
bin/gai engine install --force
bin/gai check
```

4. Update the version strings that describe the project:

```sh
grep -rn '4\.7' README.md AGENTS.md docs/gai .agents game/project.godot
```

Replace the engine version, the `config/features` value, and the doc headings.
The editor rewrites `game/project.godot` when it saves the project. Commit that
change.

5. Update each feature's `risk` if the merge showed new churn.
6. If a feature's upstream files moved or were deleted, update its manifest and
   its doc.

If Godot changes the release asset names, update `RELEASES` in `bin/gai`.

## What not to do

- Do not rebase `main`. People clone it.
- Do not resolve a conflict in a file your feature does not own. Add or update
  the owner instead.
- Do not move the base by hand. The merge command owns `.gai/upstream.json`.
- Do not merge with a dirty tree.
- Do not call the merge done before the engine builds.

## Check ownership

```sh
bin/gai upstream check
bin/gai upstream report
```

Both commands need full history. A shallow clone cannot verify the base.
