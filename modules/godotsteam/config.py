import os

# gai: the Steamworks SDK is Valve's, not MIT, and is not vendored in this
# repository. Without it the module cannot compile, so skip the module and
# point at the installer instead of failing the whole build at link time.
_SUPPORTED = ("linuxbsd", "windows", "macos", "server", "android")


def _has_sdk():
    root = os.path.dirname(os.path.abspath(__file__))
    return os.path.exists(os.path.join(root, "sdk", "public", "steam", "steam_api_flat.h"))


def can_build(env, platform):
    if platform not in _SUPPORTED:
        return False
    if not _has_sdk():
        if os.environ.get("GAI_STEAM_NOTICE") != "1":
            os.environ["GAI_STEAM_NOTICE"] = "1"
            print(
                "gai: Steamworks SDK not found, so the Steam module is off. "
                "Run `bin/gai steam sdk --download` and build again to enable it."
            )
        return False
    return True


def configure(env):
    pass


def get_doc_classes():
    return [
        "Steam",
        "SteamMultiplayerPeer",
        "SteamPacketPeer",
        "SteamProjectSettings"
        ]


def get_doc_path():
    return "doc_classes"
