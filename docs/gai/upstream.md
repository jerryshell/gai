# Merge an upstream release

Use this when Godot publishes a new tag, for example `4.8-stable`.

## Before you start

- You are on `main` with a clean working tree.
- `bin/gai check` passes.
- You can reach github.com.

## Merge

```sh
bin/gai upstream merge 4.8-stable
```

The command adds the `upstream` remote when it is missing, fetches tags, runs
`git merge --no-commit --no-ff`, checks the result against the new base, records
the base in `.gai/upstream.json`, and commits.

If it stops with conflicts, resolve only the listed files.

| File | Policy |
| --- | --- |
| `README.md` | Keep ours. Then add any upstream fact the front door needs. |
| `version.py` | Keep `name = "gai"` and our `website`. Take upstream's `major`, `minor`, `patch`, and `status`. |
| `.gitignore` | Keep both sets of rules. |

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

```sh
bin/gai engine install --force
bin/gai check
python3 tests/test_upstream.py
```

Run the test suite. Commit any doc updates.

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
