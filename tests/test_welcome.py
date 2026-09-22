from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "welcome" / "SKILL.md"

EVENT_WORDS = (
    "you installed",
    "a session started",
    "a finding was delivered and which one it was",
    "an error",
    "install id",
    "CLI",
    "OS name",
)
RULES = ("credential-egress", "agent-blocked")
REASON_CODES = (
    "quota_exhausted",
    "policy_blocked",
    "upstream_refused",
    "provider_throttled",
)


def frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert match, "skill has no frontmatter"
    return dict(line.split(": ", 1) for line in match.group(1).splitlines())


def screen(text: str) -> list[str]:
    blocks = re.findall(r"^```\n(.*?)^```", text, re.S | re.M)
    assert blocks, "skill has no fenced screen"
    return blocks[0].splitlines()


class WelcomeSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SKILL.read_text(encoding="utf-8")

    def test_only_a_person_starts_the_welcome(self) -> None:
        meta = frontmatter(self.text)
        self.assertEqual(meta["name"], "welcome")
        self.assertEqual(meta["disable-model-invocation"], "true")

    def test_screen_fits_an_eighty_column_terminal_with_a_gutter(self) -> None:
        for line in screen(self.text):
            self.assertLessEqual(len(line), 72, repr(line))

    def test_wordmark_rows_are_the_same_width(self) -> None:
        rows = [line for line in screen(self.text) if line.strip()][:3]
        self.assertEqual(len(rows), 3)
        self.assertEqual({len(row) for row in rows}, {len(rows[0])})
        self.assertTrue(rows[1].endswith(" "), "row two needs its trailing space")

    def test_screen_names_every_event_before_the_question(self) -> None:
        lines = screen(self.text)
        question = next(
            i for i, line in enumerate(lines) if line.lstrip().startswith("> Opt in")
        )
        above = " ".join("\n".join(lines[:question]).split())
        for needle in EVENT_WORDS + RULES + REASON_CODES:
            self.assertIn(needle, above)
        self.assertIn("stacktrace telemetry show", "\n".join(lines[question:]))

    def test_screen_offers_two_answers_and_highlights_opt_in(self) -> None:
        options = [line for line in screen(self.text) if "Opt " in line]
        self.assertEqual(len(options), 2)
        self.assertTrue(options[0].lstrip().startswith("> Opt in"))
        self.assertIn("(default)", options[0])
        self.assertTrue(options[1].lstrip().startswith("Opt out"))

    def test_skill_hands_the_setting_to_the_cli(self) -> None:
        self.assertIn("`stacktrace telemetry on`", self.text)
        self.assertIn("`stacktrace telemetry off`", self.text)
        self.assertNotIn("preferences", self.text)
        self.assertNotIn("stacktrace-plugin.json", self.text)

    def test_skill_states_the_no_color_fallback(self) -> None:
        self.assertIn("NO_COLOR", self.text)
        self.assertIn("`  STACKTRACE`", self.text)


if __name__ == "__main__":
    unittest.main()
