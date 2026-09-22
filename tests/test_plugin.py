from __future__ import annotations

import json
import re
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


class WelcomeScreenTests(unittest.TestCase):
    """The screen is a claim, and it is written down twice."""

    @staticmethod
    def _screen(text: str) -> str:
        blocks = re.findall(r"```\n(.*?)```", text, re.S)
        matching = [block for block in blocks if "DETECTION POLICIES" in block]
        assert len(matching) == 1, f"expected one screen, found {len(matching)}"
        return matching[0]

    def test_the_skill_prints_the_screen_the_adr_specifies(self) -> None:
        """Two copies of the same screen drift, and the drift is invisible:
        the ADR is what review reads and the skill is what a user sees."""
        adr = (
            ROOT / "docs" / "adrs"
            / "0006-welcome-someone-once-and-ask-about-analytics-there.md"
        ).read_text(encoding="utf-8")
        skill = (ROOT / "skills" / "welcome" / "SKILL.md").read_text(encoding="utf-8")

        self.assertEqual(self._screen(skill), self._screen(adr))

    def test_the_wordmark_rows_are_the_same_width(self) -> None:
        """Row two ends in a trailing space. Without it the `E` sits a column
        short, and every editor that strips trailing whitespace breaks it."""
        skill = (ROOT / "skills" / "welcome" / "SKILL.md").read_text(encoding="utf-8")
        rows = [
            line for line in self._screen(skill).split("\n")
            if any(glyph in line for glyph in "\u250c\u2514\u251c\u2534\u252c\u2524")
        ][:3]

        self.assertEqual(len(rows), 3)
        self.assertEqual({len(row) for row in rows}, {32})

    def test_the_screen_fits_an_eighty_column_terminal(self) -> None:
        skill = (ROOT / "skills" / "welcome" / "SKILL.md").read_text(encoding="utf-8")
        too_wide = [line for line in self._screen(skill).split("\n") if len(line) > 72]

        self.assertEqual(too_wide, [])

    def test_the_welcome_never_says_opt_in(self) -> None:
        """Usage metrics are on before the screen appears (ADR-0039), so there
        is nothing to opt into and saying so would be untrue."""
        skill = (ROOT / "skills" / "welcome" / "SKILL.md").read_text(encoding="utf-8")

        self.assertNotIn("opt in", self._screen(skill).lower())


if __name__ == "__main__":
    unittest.main()
