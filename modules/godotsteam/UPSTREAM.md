# GodotSteam

Vendored from https://codeberg.org/godotsteam/godotsteam at commit
`3513509dc7349f479378b0f2af2b96107f08c157` (GodotSteam 4.23.2,
2026-10-16). License: MIT, see `license.md`.

GodotSteam targets Godot 4.7 for this release. It needs Steamworks SDK 1.65.

## Files taken

- `godotsteam.cpp`, `godotsteam.h`
- `godotsteam_constants.h`, `godotsteam_enums.h`
- `godotsteam_multiplayer_peer.cpp`, `godotsteam_multiplayer_peer.h`
- `godotsteam_project_settings.cpp`, `godotsteam_project_settings.h`
- `register_types.cpp`, `register_types.h`
- `steam_packet_peer.cpp`, `steam_packet_peer.h`
- `SCsub`, `config.py`
- `doc_classes/`, `license.md`

Not taken: `godot-cpp/` and the GDExtension build files (`SConstruct`,
`build_profile.json`, `godotsteam.gdextension`), the editor updater
`plugin/`, `icons/`, `misc/`, and packaging files. gai builds Steam as an
engine module, not as an extension.

`sdk/` is empty by design. Run `bin/gai steam sdk --download`.

## Local change

`config.py` is patched to skip the module when the SDK is missing. The patch
is `gai.patch`, applied by `bin/gai steam vendor`. Keep it small, so an
upstream update stays a copy plus one patch.

## Update

```sh
git clone --depth 1 https://codeberg.org/godotsteam/godotsteam.git /tmp/godotsteam
bin/gai steam vendor --from /tmp/godotsteam
bin/gai steam sdk --from /path/to/steamworks_sdk_<version>
scons platform=linuxbsd target=editor dev_build=no linker=lld accesskit=no -j2
python3 tests/test_steam.py
```

GodotSteam does not accept patches or issues written with an LLM. Never send
them our changes, our agent output, or this patch. Keep local.
