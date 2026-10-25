# Steam

gai builds [GodotSteam](https://godotsteam.com) into the engine as a module.
`Steam` is a native class and a singleton, so the agent bridge reaches it with
no bridge code.

The vendored release is GodotSteam 4.23.2, commit
`3513509dc7349f479378b0f2af2b96107f08c157`. It targets Godot 4.7 and needs
Steamworks SDK 1.65.

## The SDK

The Steamworks SDK is Valve's, not MIT. gai does not commit it. Install it once:

```sh
bin/gai steam sdk --download
```

That downloads the pinned SDK from a public mirror and prints Valve's license
notice. If you already have the SDK from Valve, pass it instead:

```sh
bin/gai steam sdk --from ~/Downloads/steamworks_sdk_165.zip
```

`bin/gai steam status` shows the module, the SDK, and the runtime library. The
SDK lands in `modules/godotsteam/sdk/`, which is gitignored.

## Build

`bin/gai bootstrap` builds the module when the SDK is present, then copies
`libsteam_api.so` (or the platform equivalent) next to the editor binary. The
module links it with an `$ORIGIN` runtime path, so the game finds the library
without `LD_LIBRARY_PATH`.

Without the SDK, `config.py` skips the module and the build prints a line that
names the install command. The rest of the engine builds as usual.

`bootstrap` builds only when the editor binary is missing. If you install the
SDK after a build, run the `scons` command once. `bin/gai steam status` reports
whether the engine has Steam.

## Use

```gdscript
func _ready() -> void:
	var result := Steam.steamInitEx()
	if result["status"] != 0:
		print("Steam is not available: ", result["verbal"])
```

Settings live under `steam/` in `project.godot`. Auto init is off by default, so
a headless run does not touch Steam unless the game asks. The classes are
`Steam`, `SteamProjectSettings`, `SteamMultiplayerPeer`, and `SteamPacketPeer`.

## From an agent

```sh
bin/gai agent start
bin/gai agent call classdb.class '{"name":"Steam"}'
bin/gai agent call object.singleton '{"name":"Steam"}'
bin/gai agent call object.call \
  '{"handle":"<handle>","method":"steamInitEx","args":[480]}'
```

The last call returns a dictionary with `status` and `verbal`. With no Steam
client it returns a failure status and a sentence that says why. It does not
crash the game.

`tests/test_steam.py` checks the classes, both singletons, the registered
settings, a failed init without a client, and the runtime library next to the
engine.

## License

The module is MIT, see `modules/godotsteam/license.md`. The SDK is Valve's and
is covered by the Steamworks SDK license. gai downloads it but does not
redistribute it. A gai clone without the SDK still builds and runs.

GodotSteam does not accept issues or patches written with an LLM. Keep local
changes local. Never open a pull request or issue upstream with gai changes.

## Limits

- This is the standard module, not the server flavor.
- Export templates need their own build with the module. `bin/gai check` uses
  the editor binary.
- The bridge lists and emits signals. It does not connect or await them.
- Success paths need a running Steam client and a real app id. CI covers the
  failure path, the class surface, and the settings.
