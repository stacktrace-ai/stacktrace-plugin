from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PluginContractTests(unittest.TestCase):
    def test_only_stop_and_session_end_run_automatically(self) -> None:
        hooks = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))[
            "hooks"
        ]

        self.assertEqual(set(hooks), {"Stop", "SessionEnd"})
        for groups in hooks.values():
            self.assertEqual(len(groups), 1)
            self.assertNotIn("matcher", groups[0])
            self.assertEqual(len(groups[0]["hooks"]), 1)
            handler = groups[0]["hooks"][0]
            self.assertEqual(handler["type"], "command")
            self.assertIs(handler["async"], True)
            self.assertEqual(
                handler["command"],
                '"${CLAUDE_PLUGIN_ROOT}"/scripts/launch_auto_sync.py',
            )

    def test_setup_requires_confirmation_and_never_accepts_a_token(self) -> None:
        setup = (ROOT / "skills/setup/SKILL.md").read_text(encoding="utf-8")

        self.assertIn("Only after the user confirms", setup)
        self.assertIn("stacktrace remote configure", setup)
        self.assertIn("stacktrace remote auto-sync enable", setup)
        self.assertIn("Do not ask the user to paste a token", setup)
        self.assertNotIn("--token", setup)

    def test_plugin_contains_no_credential_or_sync_state(self) -> None:
        payload_files = [
            ROOT / ".claude-plugin/plugin.json",
            ROOT / ".claude-plugin/marketplace.json",
            ROOT / "hooks/hooks.json",
            ROOT / "scripts/launch_auto_sync.py",
            *(ROOT / "skills").glob("*/SKILL.md"),
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in payload_files)

        self.assertNotIn("api_key", text.lower())
        self.assertNotIn("remote.toml", text)
        self.assertFalse((ROOT / ".mcp.json").exists())
        self.assertFalse((ROOT / "settings.json").exists())


if __name__ == "__main__":
    unittest.main()
