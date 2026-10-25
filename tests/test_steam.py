#!/usr/bin/env python3
"""End-to-end tests for the Steam module. Needs a source build with the Steamworks SDK."""

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def built_engine():
    for path in sorted((ROOT / "bin").glob("godot.*.editor.*")):
        if ".console." in path.name or path.name.endswith(".debug"):
            continue
        if path.is_file():
            return path
    return None


ENGINE = built_engine() or os.environ.get("GAI_GODOT")


class SteamTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gai-steam-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "bin").mkdir()
        shutil.copy2(ROOT / "bin" / "gai", self.tmp / "bin" / "gai")
        shutil.copytree(
            ROOT / "game",
            self.tmp / "game",
            ignore=shutil.ignore_patterns(".godot"),
        )
        (self.tmp / ".gai").mkdir()
        (self.tmp / ".gai" / "version").write_text("0.0.0-test\n", encoding="utf-8")
        self.env = dict(os.environ)
        self.env["GAI_GODOT"] = str(ENGINE)
        started = self.run_gai("agent", "start")
        if started.returncode != 0:
            self.skipTest("cannot start the agent bridge: " + started.stderr.strip())
        self.addCleanup(self.run_gai, "agent", "stop")
        if "unknown class: Steam" in self.run_gai("agent", "call", "classdb.class", '{"name":"Steam"}').stderr:
            self.skipTest("the engine was built without the Steamworks SDK")

    def run_gai(self, *args, timeout=60):
        return subprocess.run(
            [sys.executable, str(self.tmp / "bin" / "gai"), *map(str, args)],
            cwd=str(self.tmp),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            timeout=timeout,
        )

    def call(self, method, params=None):
        result = self.run_gai("agent", "call", method, json.dumps(params or {}))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def singleton(self, name):
        return self.call("object.singleton", {"name": name})

    def test_class_surface(self):
        info = self.call("classdb.class", {"name": "Steam"})
        methods = {method["name"] for method in info["methods"]}
        for name in ("steamInit", "steamInitEx", "steamShutdown", "run_callbacks", "getAppID"):
            self.assertIn(name, methods)
        for name in ("SteamMultiplayerPeer", "SteamPacketPeer", "SteamProjectSettings"):
            other = self.call("classdb.class", {"name": name})
            self.assertEqual(other["name"], name)

    def test_singletons(self):
        for name in ("Steam", "SteamProjectSettings"):
            info = self.singleton(name)
            self.assertEqual(info["class"], name)
            self.assertTrue(info["handle"].isdigit(), info)
        names = {item["name"] for item in self.call("api.singletons")["singletons"]}
        self.assertIn("Steam", names)
        self.assertIn("SteamProjectSettings", names)

    def test_settings_are_registered(self):
        value = self.call(
            "project.get",
            {"key": "steam/initialization/processes/initialize_on_startup"},
        )
        self.assertIs(value, False)

    def test_init_without_a_steam_client(self):
        handle = self.singleton("Steam")["handle"]
        result = self.call(
            "object.call",
            {"handle": handle, "method": "steamInitEx", "args": [480, False]},
        )
        self.assertIn("status", result)
        self.assertIn("verbal", result)
        self.assertIsInstance(result["status"], int)
        self.assertIsInstance(result["verbal"], str)
        if result["status"] == 0:
            self.call("object.call", {"handle": handle, "method": "steamShutdown", "args": []})
        else:
            self.assertTrue(result["verbal"], "a failed init must say why")

    def test_runtime_library_sits_next_to_the_engine(self):
        system = platform.system()
        if system == "Linux":
            name = "libsteam_api.so"
        elif system == "Darwin":
            name = "libsteam_api.dylib"
        elif system == "Windows":
            name = "steam_api64.dll"
        else:
            self.skipTest(f"no Steam library for {system}")
        self.assertTrue((ENGINE.parent / name).is_file(), f"{name} is missing next to {ENGINE}")


if __name__ == "__main__":
    unittest.main()
