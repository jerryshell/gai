# C# .NET web export

Status: planned
Risk: high
Manifest: `.gai/features/dotnet-web.json`

## Current fact

Godot 4.7.2 refuses .NET web export in the engine source.
`platform/web/export/export_plugin.cpp:425` returns failure when
`MODULE_MONO_ENABLED` is set:

```text
Exporting to Web is currently not supported in Godot 4 when using C#/.NET.
```

I downloaded the official `4.7.2-stable_mono_linux_x86_64` editor and ran:

```sh
Godot_v4.7.2-stable_mono_linux.x86_64 --headless --path <project> --export-release Web <out>/index.html
```

It failed with the same message. The check also rejects a project that does not
use C# when the editor is a .NET build. The run is recorded in
`docs/gai/decisions/worklog.tsv`.

Deleting that one guard is not enough. The export needs a .NET WebAssembly
runtime, custom web templates, and a matching engine build.

## Available work

- `raulsntos` wrote the experimental engine support:
  https://github.com/raulsntos/godot4-web-dotnet-prototype
- `ComplexRobot/godot-dotnet-web-export` publishes a fork and prebuilt binaries:
  https://github.com/ComplexRobot/godot-dotnet-web-export
- Its releases are for `4.8-dev7` (2026-09-30), Windows only, about 162 MB:
  https://github.com/ComplexRobot/godot-dotnet-web-export/releases
- It requires .NET 9, the `wasm-tools` workload, and custom web templates.
- Its README lists limits: no GDExtensions, no globalization, some BCL APIs do
  not work, and the host must send SharedArrayBuffer headers.
- It is not based on 4.7.2.

## Options

| Option | Cost | Risk |
| --- | --- | --- |
| Move gai to 4.8-dev | New engine base and new merges | Unstable base |
| Backport the work to 4.7.2 | Port the web and mono changes | Unknown effort |
| Wait for 4.8-stable | No work now | Delay |
| Ship the Windows-only fork binary | Use a third-party build | Not cross-platform |

## Build needs

- Emscripten SDK.
- .NET 9 SDK and the `wasm-tools` workload.
- Custom web export templates.
- A machine with enough RAM and CPU for the Godot web build and the .NET
  WebAssembly build.

This server has 2 vCPU and 3 GB RAM. It is not a build machine for this feature.

## Verification

1. Export a small C# project to a directory.
2. Serve the directory with COOP and COEP headers.
3. Load it in Chromium and wait for the canvas.
4. Read the browser console, take a screenshot, and assert that the scene ran.
5. Repeat on every upstream merge while the feature is active.

A stub export or a compiled template is not proof. The page must load and run.

## Decision

Do not set the feature to `active` until the base version and the build platform
are chosen. Do not claim .NET web support before a real export runs in a browser.
