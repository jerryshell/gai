# 0002 Use one CLI as the agent surface

Date: 2026-10-25
Status: accepted

## Context

An agent must be able to run the game, check it, and keep the engine close to
upstream. The same interface must work in pi, opencode, a terminal, and CI. The
machine may have no display.

## Options

| Option | What it adds | Cost |
| --- | --- | --- |
| `bin/gai` CLI | One Python file, plain text output | No structured editor state |
| MCP server | Typed tools, a protocol | A second process, client configuration, another surface to test |
| Editor plugin | An AI panel inside Godot | Engine C++ and UI code in the gai layer, GUI only |
| Build system integration | A custom SCons target | Ties every workflow to a full engine build |

## Decision

Use one CLI. Agents already have a shell, and every check is a process that
returns text and an exit code. `check` wraps the three engine stages that Godot
does not chain for you.

## Consequences

- Agents edit scenes as text and verify with `check`. The skill documents the
  format.
- CI runs the same commands as a person or an agent.
- No feature depends on editor state that a headless process cannot read.
- Revisit this decision when a feature needs live editor state, such as a scene
  graph the engine will not print.
