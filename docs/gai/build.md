# Build the engine

The repository is a Godot source tree. Build it to change engine code or to run a
binary with the gai display name. For game work, `bin/gai engine install` is
enough.

## Requirements

- Python 3.8 or later.
- SCons 4.x. Install it with `pip install scons` or your package manager.
- A C++17 compiler and the platform dependencies from the Godot docs.

Godot 4.7 build docs:
https://docs.godotengine.org/en/4.7/contributing/development/compiling/

## Build

From the repository root:

```sh
scons platform=linuxbsd target=editor dev_build=no -j$(nproc)
```

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

## Run the build

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

## Build gate for engine features

`bin/gai check` tests the game, not the engine. An engine change needs an editor
build and the feature tests before you commit. The current CI does not build the
engine yet. That is the next infrastructure piece.

## .NET web export

The .NET web export is a planned feature. It needs a custom engine build and
custom web templates, not the normal `scons` command. See
`features/dotnet-web.md`.
