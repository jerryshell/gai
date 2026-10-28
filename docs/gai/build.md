# Build the engine

The repository is a Godot source tree. `bin/gai build` builds the gai engine
from source. It rebuilds when an engine source file is newer than the editor
binary. `bin/gai bootstrap` uses the same check on the first run, then runs the
game check. The official fallback is for machines that cannot build; it has no
gai display name and no agent bridge.

## Requirements

- Python 3.8 or later.
- SCons 4.x. Install it with `pip install scons` or your package manager.
- A C++17 compiler and the platform dependencies from the Godot docs.

Godot 4.7 build docs:
https://docs.godotengine.org/en/4.7/contributing/development/compiling/

## Build

From the repository root:

```sh
bin/gai build
```

`--check` exits 0 when the binary is current and 1 when a rebuild is needed.
`--force` rebuilds even when it is current. `--dry-run` prints the SCons command.
`--jobs N` overrides the memory-aware default. The command keeps the platform
flags in one place; on Linux with `lld` installed it adds `linker=lld` and
`accesskit=no`. A build removes `game/.godot`; run `bin/gai check` to import
again.

To run SCons yourself:

```sh
scons platform=linuxbsd target=editor dev_build=no -j$(nproc)
```

On a 2-core machine with 3.8 GB RAM and 4 GB swap, this repository built the
editor in 71 minutes with:

```sh
scons platform=linuxbsd target=editor dev_build=no linker=lld accesskit=no -j2
```

`accesskit=no` drops screen reader support. Use it only when its dependencies
are not installed.

macOS:

```sh
scons platform=macos target=editor dev_build=no -j$(sysctl -n hw.ncpu)
```

Windows, in PowerShell:

```powershell
scons platform=windows target=editor dev_build=no
```

A clean editor build takes tens of minutes on a many-core machine and hours on a
small one. Keep several GB of free disk for each target.

## After switching engines

If you switch between the downloaded engine and a source build, delete
`game/.godot` before the first run. An import left by the other binary can crash
on exit with `Parameter "singleton" is null`. The next import rebuilds the cache.

## Run the build

The source build includes the agent bridge (`modules/gai_agent/`). The
downloaded engine does not.

The binary lands in `bin/`:

```text
bin/godot.linuxbsd.editor.x86_64
```

`bin/gai` finds a built editor binary before the downloaded one. Check which one
it uses:

```sh
bin/gai doctor
```

To use a specific binary:

```sh
GAI_GODOT=/path/to/godot bin/gai check
```

## See the brand

Start the editor or the game. The window title and the startup header use the
`name` value in `version.py`.

```sh
./bin/godot.linuxbsd.editor.x86_64 --path game --editor
```

## Steam

The engine includes GodotSteam when the Steamworks SDK is installed:

```sh
bin/gai steam sdk --download
scons platform=linuxbsd target=editor dev_build=no linker=lld accesskit=no -j2
```

The SDK is Valve's and is not committed. Without it, the build skips the module
and says so. `bin/gai steam status` reports the SDK and the runtime library.
The module links `libsteam_api.so` with an `$ORIGIN` runtime path, so the library
must sit next to the editor binary. `bin/gai` copies it there.

## Web export

A project needs a `Web` export preset and Godot's web export templates. The
templates for 4.7.2 live in `~/.local/share/godot/export_templates/4.7.2.stable/`
on Linux:

```sh
bin/gai export web --clean --gzip
```

The command writes `build/web/index.html`, adds `.gdignore` in the output so
Godot does not import the exported files, and with `--gzip` writes `.gz` files
for a static server with `gzip_static`. It checks that `index.html`,
`index.wasm`, and `index.pck` exist.

The gai engine uses Godot's official web template today. The web runtime is
stock Godot, so the agent bridge and Steam are not in it. A custom gai web
template needs Emscripten and is not built yet.

## Build gate for engine features

`bin/gai check` tests the game, not the engine. An engine change needs an editor
build and the feature tests before you commit. CI builds the editor and runs the
agent and Steam tests in the `engine` job.

## .NET web export

The .NET web export is a planned feature. It needs a custom engine build and
custom web templates, not the normal `scons` command. See
`features/dotnet-web.md`.
