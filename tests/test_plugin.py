from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
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


def _session_start(preferences: str | None = None, **environment: str) -> str:
    """The additionalContext the hook emits for a given environment and file."""
    with tempfile.TemporaryDirectory() as home:
        if preferences is not None:
            claude = Path(home) / ".claude"
            claude.mkdir()
            (claude / "stacktrace-plugin.json").write_text(preferences, encoding="utf-8")
        result = subprocess.run(
            ["sh", str(ROOT / "scripts" / "session_start.sh")],
            check=True,
            capture_output=True,
            text=True,
            input='{"untrusted":"input"}',
            env={**os.environ, "HOME": home, **environment},
        )
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


class AlertRenderingTests(unittest.TestCase):
    """The alert is produced by the model, so the specification is the artefact.

    Nothing in this plugin formats an alert. What can be asserted is the
    contract the hook hands the model, which is the only thing that makes one
    session's alert look like the next one's.
    """

    def test_severity_and_confidence_are_specified_as_separate_grades(self) -> None:
        context = _session_start()
        self.assertIn("Stacktrace alert rendering:", context)
        self.assertIn("two separate grades", context)
        self.assertIn("Never merge them into one word", context)

    def test_absent_confidence_is_stated_and_never_inferred(self) -> None:
        # The wire strips every event to five fields and confidence is not one
        # of them, so the only honest rendering says so. A specification that
        # let the model reach for the severity instead would print a grade the
        # daemon never sent.
        context = _session_start()
        self.assertIn("confidence unstated", context)
        self.assertIn("Never infer a confidence from a severity", context)

    def test_no_color_drops_the_glyph_and_keeps_the_words(self) -> None:
        coloured = _session_start(NO_COLOR="")
        plain = _session_start(NO_COLOR="1")
        self.assertIn("severity glyph", coloured)
        self.assertIn("omit the glyph", plain)
        self.assertIn("keep every word", plain)
        self.assertNotIn("omit the glyph", coloured)


class DesktopPreferenceTests(unittest.TestCase):
    def test_no_file_means_desktop_notifications_stay_on(self) -> None:
        self.assertIn("Desktop notifications are on", _session_start())

    def test_explicit_false_turns_them_off(self) -> None:
        context = _session_start('{"desktop_notifications": false}')
        self.assertIn("turned desktop notifications off", context)
        self.assertIn("Do not call PushNotification", context)
        # The conversation alert is never silenced with the desktop banner.
        self.assertIn("Still show the alert in this conversation", context)

    def test_true_and_malformed_both_leave_them_on(self) -> None:
        # Absent, unreadable and malformed mean the same thing: the user has not
        # turned them off. Only an explicit false does.
        for preferences in ('{"desktop_notifications": true}', "{", "", "null"):
            with self.subTest(preferences=preferences):
                self.assertIn("Desktop notifications are on", _session_start(preferences))

    def test_preferences_cannot_reshape_the_document(self) -> None:
        # The file is read by the hook, but every branch emits a fixed string
        # the hook controls, so nothing from the file reaches the JSON.
        hostile = '{"desktop_notifications": false, "x": "\\" injected"}'
        context = _session_start(hostile)
        self.assertNotIn("injected", context)

    def test_the_hook_still_reads_nothing_from_its_input(self) -> None:
        for preferences in (None, '{"desktop_notifications": false}'):
            with self.subTest(preferences=preferences):
                self.assertNotIn("untrusted", _session_start(preferences))


class OnboardingSkillTests(unittest.TestCase):
    SKILL = ROOT / "skills" / "onboarding" / "SKILL.md"

    @classmethod
    def body(cls) -> str:
        """The skill with its line wrapping collapsed.

        These assertions are about what the skill says, not where it wraps.
        """
        return " ".join(cls.SKILL.read_text(encoding="utf-8").split())

    def test_onboarding_is_user_invoked_only(self) -> None:
        self.assertIn("disable-model-invocation: true", self.body())

    def test_it_does_not_ask_the_policy_question(self) -> None:
        body = self.body()
        self.assertIn("Two questions", body)
        self.assertIn("that is a policy question", body.replace("That is", "that is"))

    def test_slack_is_handed_to_the_cli_and_no_token_is_read(self) -> None:
        body = self.body()
        self.assertIn("stacktrace slack connect", body)
        self.assertIn("Never read a credential file into the conversation", body)
        self.assertIn("never ask the user to paste a token", body)
        self.assertIn("never print a recipient id", body)

    def test_the_only_file_written_is_the_preferences_file(self) -> None:
        body = self.body()
        self.assertIn("~/.claude/stacktrace-plugin.json", body)
        self.assertIn("is the only file this plugin writes", body)
        self.assertIn("no delivery state ever goes in it", body)

    def test_the_config_is_written_by_the_script_not_by_hand(self) -> None:
        # A model writing this file by hand can replace it instead of updating
        # it, or record a key the hook does not read. Neither is visible
        # afterwards, which is why the skill is told to shell out.
        body = self.body()
        self.assertIn("scripts/preferences.py", body)
        self.assertIn("Do not write the file by hand", body)

    def test_slack_has_no_stored_preference(self) -> None:
        # A second copy of "is Slack on" would go stale against the adapter.
        self.assertIn("There is no Slack preference to store", self.body())


if __name__ == "__main__":
    unittest.main()
