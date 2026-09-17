from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PluginContractTests(unittest.TestCase):
    def test_automatic_events_are_exactly_the_documented_three(self) -> None:
        hooks = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))[
            "hooks"
        ]
        launcher = '"${CLAUDE_PLUGIN_ROOT}"/scripts/launch_auto_sync.py'
        detector = '"${CLAUDE_PLUGIN_ROOT}"/scripts/detect_and_notify.py'

        self.assertEqual(set(hooks), {"Stop", "SessionEnd", "PostToolUseFailure"})
        for groups in hooks.values():
            self.assertEqual(len(groups), 1)
            self.assertNotIn("matcher", groups[0])
            self.assertEqual(len(groups[0]["hooks"]), 1)

        # Sync work stays detached on both lifecycle events.
        for event in ("Stop", "SessionEnd"):
            handler = hooks[event][0]["hooks"][0]
            self.assertEqual(handler["command"], launcher)
            self.assertIs(handler["async"], True)

        # ADR-0002: the detector is the one synchronous hook, because an async
        # hook's stdout is never read and so can never show anyone a finding.
        self.assertEqual(
            hooks["PostToolUseFailure"][0]["hooks"][0],
            {"type": "command", "command": detector, "timeout": 5},
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
