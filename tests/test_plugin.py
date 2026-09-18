from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PluginContractTests(unittest.TestCase):
    def test_validator_accepts_the_repository(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_plugin.py")],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "plugin scaffold ok\n")

    def test_session_start_emits_only_the_notification_contract(self) -> None:
        result = subprocess.run(
            ["sh", str(ROOT / "scripts" / "session_start.sh")],
            check=True,
            capture_output=True,
            text=True,
            input='{"untrusted":"input"}',
        )
        document = json.loads(result.stdout)
        output = document["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "SessionStart")
        context = output["additionalContext"]
        self.assertIn("STACKTRACE_NOTIFY_V1", context)
        self.assertIn("PushNotification", context)
        self.assertNotIn("untrusted", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_plugin_has_no_turn_or_session_end_detection_hook(self) -> None:
        document = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(set(document["hooks"]), {"SessionStart"})

    def test_monitor_invokes_the_stacktrace_subscription_directly(self) -> None:
        monitors = json.loads(
            (ROOT / "monitors" / "monitors.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(monitors), 1)
        self.assertEqual(
            monitors[0]["command"], "stacktrace daemon subscribe --agent-kind claude-code"
        )


    def test_skills_name_the_session_variable_claude_actually_sets(self) -> None:
        # Claude Code exports CLAUDE_CODE_SESSION_ID. A skill that reads
        # CLAUDE_SESSION_ID gets an empty string and passes it as a real
        # argument, which fails as a missing session rather than as a typo.
        for skill in sorted((ROOT / "skills").glob("*/SKILL.md")):
            with self.subTest(skill=skill.parent.name):
                body = skill.read_text(encoding="utf-8")
                self.assertNotIn("CLAUDE_SESSION_ID", body)

    def test_plugin_contains_no_credential_or_sync_state(self) -> None:
        payload_files = [
            ROOT / ".claude-plugin/plugin.json",
            ROOT / ".claude-plugin/marketplace.json",
            ROOT / "hooks/hooks.json",
            ROOT / "monitors/monitors.json",
            ROOT / "scripts/session_start.sh",
            *(ROOT / "skills").glob("*/SKILL.md"),
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in payload_files)

        self.assertNotIn("api_key", text.lower())
        self.assertNotIn("remote.toml", text)
        self.assertFalse((ROOT / ".mcp.json").exists())
        self.assertFalse((ROOT / "settings.json").exists())


if __name__ == "__main__":
    unittest.main()
