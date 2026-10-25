# 0003 Deep fork with feature-owned divergence

Date: 2026-10-26
Status: accepted
Supersedes: 0001

## Context

The first design optimized for cheap upstream merges. It kept a thin allowlist,
edited three upstream files, and failed any other divergence. That design made
the product impossible. gai is centered on AI-native engine work, and the engine
must change: an agent bridge, headless verification, and platform features such
as .NET web export.

A thin-layer rule protects the merge process at the cost of the product. The
product comes first. Upstream tracking stays a maintenance requirement, not a
design limit.

## Decision

- gai is a deep fork. Engine changes are part of the product.
- Every engine change is claimed by an active feature in `.gai/features/`.
- `bin/gai upstream check` enforces ownership, not a size limit. It fails on an
  engine path that no active feature claims.
- `main` merges Godot tags. Conflicts are expected. The feature that claims a
  file resolves its conflict, rebuilds the engine, and reruns its tests.
- A build gate is required. The current CI does not build the engine yet, and
  that is the next infrastructure piece.
- The first vertical AI-native feature is the engine agent bridge. The .NET web
  export is a separate high-risk feature.

## Alternatives

| Option | Why not |
| --- | --- |
| Keep the thin layer | It forbids the engine work the product exists for. |
| Rebase on each upstream tag | Rewrites public history and still conflicts. |
| Vendor the engine | Loses upstream ancestry and merge capability. |
| Drop upstream tracking | The fork becomes unmaintainable against security and engine fixes. |

## Consequences

- Upstream merges cost more. High-risk features pay for a build and a test after
  every merge.
- The repository can implement deep engine features, including .NET web export,
  subject to build cost and platform support.
- The allowlist model and its guard are removed.
- Feature manifests are the source of truth for who owns which engine path.
