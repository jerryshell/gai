# 0001 Keep a thin layer over upstream

Date: 2026-10-25
Status: accepted

## Context

gai must ship a Godot-based engine and keep taking Godot releases. The first base
is `4.7.2-stable`. The next is `4.8`.

## Options

| Option | Cost per release | Risk |
| --- | --- | --- |
| Merge upstream tags into `main` | One merge commit, conflicts limited to the allowlist | The allowlist can grow by accident |
| Rebase gai commits onto the new tag | Rewrites public history | Every clone must reset |
| Rebrand every upstream file | Resolve conflicts across the UI and build files | Merge cost grows with every release |
| Vendor the engine in a subdirectory | No upstream ancestry | Cannot merge future releases |

## Decision

Merge upstream tags into `main`. Keep gai files in owned paths. Edit three
upstream files: `README.md`, `version.py`, and `.gitignore`. Record the base
commit in `.gai/upstream.json`. Enforce the allowlist in `bin/gai upstream check`
and in CI.

## Consequences

- A release merge is one command, plus a README resolution when upstream edits
  its README.
- Every gai addition must fit an owned path, or the check fails.
- `short_name` and the built binary name stay `godot`, because the build system
  depends on them. Branding reaches the window title, version header, and crash
  reports through `version.py`.
- A full UI rebrand stays out of scope. It would move many upstream files into
  the allowlist.
