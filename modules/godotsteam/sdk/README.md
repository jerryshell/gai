# Steamworks SDK

This directory holds Valve's Steamworks SDK. It is not part of the gai
repository and is not covered by gai's MIT license. Your use of the SDK is
governed by the Steamworks SDK license from Valve.

Install it with:

```sh
bin/gai steam sdk --download
```

Or copy an SDK you already have:

```sh
bin/gai steam sdk --from /path/to/steamworks_sdk_165
```

The script copies `public/` and `redistributable_bin/` only. Keep the SDK
version in step with `modules/godotsteam/UPSTREAM.md`.
