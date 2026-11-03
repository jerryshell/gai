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

`--check` exits 0 when the binary is current and 1 when a rebuild is needed. It
answers from content, not mtimes: a successful build writes
`.gai/build/<target>-<host>.json` with a tree hash of each engine directory and a
content hash of every dirty file the build reads, and `--check` compares both. A checkout,
a formatter pass that rewrites the same bytes, or a merge of branches that touched
no engine file no longer reads as a reason to rebuild.

`--force` rebuilds even when it is current. `--dry-run` prints the SCons command.
`--jobs N` overrides the memory-aware default. The command keeps the platform
flags in one place; on Linux with `lld` installed it adds `linker=lld` and
`accesskit=no`. A build keeps `game/.godot`. Pass `--clean-import` after an
engine or import-format change to make `check` import again.

Export templates:

```sh
bin/gai build --target template_release --jobs 2
bin/gai build --target template_release --platform windows --mingw --jobs 2
```

`--check`, `--force`, and `--dry-run` work with a target. A Windows template on
Linux needs MinGW. `--target template_debug` is also accepted. The output lands
in `bin/` next to the editor binary.

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

## Editor and template builds differ

`target=template_release` compiles without `TOOLS_ENABLED`. An editor-only API
such as `Script::get_documentation` does not exist there, and a change that only
an editor build compiles will break the export template and the Windows matrix.
Check one object file instead of the whole target:

```sh
scons platform=linuxbsd target=template_release dev_build=no linker=lld accesskit=no -j2 \
    bin/obj/modules/<module>/<file>.linuxbsd.template_release.x86_64.o
```

That compiles one translation unit in about five seconds. `bin/gai build
--target template_release --objects <paths>` runs the same thing for the sources
in a change set, and `bin/gai next` puts it between `build` and `check` for an
engine `.cpp` change. A header-only change skips it, because one header maps to
many objects.

## Compile cache

A compiler cache makes a rebuild much faster: an unchanged object comes from the
cache instead of the compiler. `bin/gai build` detects a cache once per build. It
looks for `sccache` first, then `ccache`, with `shutil.which`. It prints one line:

```text
build: cache ccache (/home/me/.cache/ccache)
build: cache none (install ccache or sccache for faster rebuilds)
```

The launcher does not go into `CC` directly. SCons runs `$CC` as one program, so
`CC="ccache cc"` fails with `ccache cc: not found`. gai writes two wrappers
instead, `.gai/tools/cache/ccache-cc` and `ccache-cxx`, and passes their absolute
paths:

```text
CC="/repo/.gai/tools/cache/ccache-cc" CXX="/repo/.gai/tools/cache/ccache-cxx"
```

A wrapper is one line, `exec "/usr/bin/ccache" cc "$@"`. It runs the compiler the
build already uses: `cc` and `c++` unless `CC` or `CXX` is set. A variable that
already names a launcher, as in `CC="ccache gcc"`, is left alone rather than
wrapped twice. The cache folder comes from `SCCACHE_DIR` or `CCACHE_DIR` when
that variable is set. gai does not install a cache, does not invent a compiler,
and does not change any other SCons flag or the `--jobs` default.

- `--no-cache` turns the cache off for one build.
- `--dry-run` prints the cache line and the wrapper paths.
- `--check` prints no cache line, because it does not build.
- Windows is not wired, because the wrapper is a `sh` script. The line says so.

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

## The cheapest sufficient gate

`bin/gai next` prints the cheapest gate that still proves a change. Give it the
changed paths, or let it read `git status --porcelain`:

```sh
bin/gai next game/scripts/player.gd      # gate script
bin/gai next game/scenes/main.tscn       # gate check
bin/gai next core/object/object.cpp      # gate rebuild-check
bin/gai next docs/gai/build.md           # gate none
```

The gate is `none`, `script`, `check`, or `rebuild-check`, in that order of cost.
It is the highest gate of the paths it was given:

| Change | Gate | Command |
| --- | --- | --- |
| `.gai/features/`, engine source in `core/ scene/ servers/ modules/ platform/ editor/ main/ drivers/`, `SConstruct`, `methods.py`, `version.py` | `rebuild-check` | `bin/gai build`, then `bin/gai check` |
| game scene, asset, autoload, `project.godot` | `check` | `bin/gai check` |
| a game `*.gd` script | `script` | `bin/gai check --script res://<path> --no-run` |
| `*.md`, `docs/`, `AGENTS.md`, `tests/*.py`, `.github/` | `none` | nothing |
| anything else | `check` | `bin/gai check` |

A file under `game/tests/` gives `check`, not `script`. A path that git reports
as deleted gives `check` too, because a missing script cannot be compiled and the
scenes that referenced it are what still needs a gate.

`--json` prints `gate`,
`command`, `paths`, and one `reasons` entry per path. `--run` runs the commands
and returns the exit code of the first failure; for the `script` gate it runs
`check --script` once per script and stops at the first failure.

## .NET web export

The .NET web export is a planned feature. It needs a custom engine build and
custom web templates, not the normal `scons` command. See
`features/dotnet-web.md`.
