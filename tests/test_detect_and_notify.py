from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import detect_and_notify as detector  # noqa: E402


def transcript(*entries: tuple[str, str, bool]) -> Path:
    """Write a transcript whose tool calls are (id, tool, failed) in order."""
    lines: list[str] = []
    for call_id, tool, _failed in entries:
        lines.append(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "tool_use", "id": call_id, "name": tool, "input": {}}]},
                }
            )
        )
    for call_id, _tool, failed in entries:
        lines.append(
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": call_id,
                                "is_error": "True" if failed else False,
                                "content": "AssertionError: 3 != 1" if failed else "ok",
                            }
                        ]
                    },
                }
            )
        )
    handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    handle.write("\n".join(lines) + "\n")
    handle.close()
    return Path(handle.name)


class SignatureTests(unittest.TestCase):
    def test_volatile_detail_does_not_split_one_streak(self) -> None:
        first = detector.signature("Bash", "failed after 1.2s at /tmp/run-8471/test.py")
        second = detector.signature("Bash", "failed after 9.8s at /tmp/run-2290/test.py")

        self.assertEqual(first, second)

    def test_different_tools_are_different_failures(self) -> None:
        self.assertNotEqual(detector.signature("Bash", "boom"), detector.signature("Edit", "boom"))


class StreakTests(unittest.TestCase):
    def test_streak_counts_only_the_trailing_identical_failures(self) -> None:
        path = transcript(("a", "Bash", True), ("b", "Bash", True), ("c", "Bash", True))
        self.assertEqual(detector.streak(detector.read_attempts(path)), (3, "Bash"))

    def test_a_success_breaks_the_streak(self) -> None:
        path = transcript(("a", "Bash", True), ("b", "Bash", False), ("c", "Bash", True))
        self.assertEqual(detector.streak(detector.read_attempts(path)), (1, "Bash"))

    def test_no_streak_when_the_last_call_succeeded(self) -> None:
        path = transcript(("a", "Bash", True), ("b", "Bash", False))
        self.assertIsNone(detector.streak(detector.read_attempts(path)))

    def test_unreadable_transcript_is_silent(self) -> None:
        self.assertEqual(detector.read_attempts(Path("/nonexistent/transcript.jsonl")), [])


class RenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.finding = detector.finding_for(3, "Bash")

    def test_plain_render_names_the_rule_and_both_grades(self) -> None:
        out = detector.render(self.finding, colour=False)

        self.assertNotIn("\x1b[", out)
        self.assertIn("medium · high · stacktrace-progress-stall", out)
        self.assertEqual(len(out.strip().splitlines()), 5)

    def test_severity_selects_the_gutter_colour(self) -> None:
        self.assertIn("\x1b[33m▐", detector.render(self.finding, colour=True))

    def test_colour_honours_no_color_and_the_override(self) -> None:
        self.assertTrue(detector.use_colour({}))
        self.assertFalse(detector.use_colour({"NO_COLOR": "1"}))
        self.assertFalse(detector.use_colour({"STACKTRACE_COLOR": "never"}))
        self.assertTrue(detector.use_colour({"NO_COLOR": "1", "STACKTRACE_COLOR": "always"}))

    def test_the_notice_bounds_what_claude_is_asked_to_do(self) -> None:
        notice = detector.notice_for(self.finding)

        self.assertIn("PushNotification", notice)
        self.assertIn("Do not investigate", notice)
        self.assertIn("suppresses itself", notice)


class MainTests(unittest.TestCase):
    def run_main(self, document: object, monkeypatch_stdin: str | None = None) -> str:
        import io

        stdin, stdout = sys.stdin, sys.stdout
        sys.stdin = io.StringIO(monkeypatch_stdin or json.dumps(document))
        sys.stdout = io.StringIO()
        try:
            detector.main()
            return sys.stdout.getvalue()
        finally:
            sys.stdin, sys.stdout = stdin, stdout

    def test_fires_once_at_the_threshold_and_not_after(self) -> None:
        at = transcript(*[(str(n), "Bash", True) for n in range(detector.STALL_THRESHOLD)])
        beyond = transcript(*[(str(n), "Bash", True) for n in range(detector.STALL_THRESHOLD + 1)])

        fired = self.run_main({"hook_event_name": "PostToolUseFailure", "transcript_path": str(at)})
        again = self.run_main({"hook_event_name": "PostToolUseFailure", "transcript_path": str(beyond)})

        self.assertIn("stacktrace-progress-stall", fired)
        self.assertEqual(again, "")

    def test_output_carries_both_audiences(self) -> None:
        at = transcript(*[(str(n), "Bash", True) for n in range(detector.STALL_THRESHOLD)])
        payload = json.loads(
            self.run_main({"hook_event_name": "PostToolUseFailure", "transcript_path": str(at)})
        )

        self.assertIn("systemMessage", payload)
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "PostToolUseFailure")
        self.assertIn("PushNotification", payload["hookSpecificOutput"]["additionalContext"])

    def test_unrelated_events_and_bad_input_are_silent(self) -> None:
        at = transcript(*[(str(n), "Bash", True) for n in range(detector.STALL_THRESHOLD)])

        self.assertEqual(self.run_main({"hook_event_name": "Stop", "transcript_path": str(at)}), "")
        self.assertEqual(self.run_main({"hook_event_name": "PostToolUseFailure"}), "")
        self.assertEqual(self.run_main(None, monkeypatch_stdin="not json"), "")


if __name__ == "__main__":
    unittest.main()
