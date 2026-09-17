from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import render_finding  # noqa: E402


FINDING = {
    "rule_id": "stacktrace-progress-stall",
    "severity": "medium",
    "confidence": "high",
    "title": "Same test failing since turn 22 — three attempts, no change between them",
    "evidence": ["turns 22, 26, 31 · identical failure signature", "0 successful runs in the window"],
    "recommendation": "This isn't converging. Change the approach or take it back.",
    "coverage": {"full": True, "reason": None, "note": "All three attempts were captured."},
}


def completed(payload: object, *, code: int = 0) -> subprocess.CompletedProcess[bytes]:
    body = json.dumps(payload).encode() if payload is not None else b""
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=body, stderr=b"")


class RenderTests(unittest.TestCase):
    def test_plain_render_carries_grades_rule_and_actions(self) -> None:
        out = render_finding.render(dict(FINDING, show_actions=True), colour=False)

        self.assertNotIn("\x1b[", out)
        self.assertTrue(out.startswith("\n"))
        self.assertIn("medium · high · stacktrace-progress-stall", out)
        self.assertIn("/stacktrace:dismiss", out)
        self.assertEqual(len(out.strip().splitlines()), 6)

    def test_action_row_is_omitted_unless_the_cli_asks_for_it(self) -> None:
        self.assertNotIn("/stacktrace:dismiss", render_finding.render(FINDING, colour=False))

    def test_full_coverage_is_not_stated_and_partial_coverage_is(self) -> None:
        self.assertNotIn("coverage", render_finding.render(FINDING, colour=False))

        partial = dict(FINDING, coverage={"full": False, "reason": "insufficient_context", "note": ""})
        self.assertIn("partial coverage · insufficient_context", render_finding.render(partial, colour=False))

    def test_repeat_count_appears_only_when_it_repeated(self) -> None:
        self.assertNotIn("×", render_finding.render(dict(FINDING, fired_here=1), colour=False))
        self.assertIn("×4 here", render_finding.render(dict(FINDING, fired_here=4), colour=False))

    def test_severity_selects_the_gutter_colour(self) -> None:
        high = render_finding.render(dict(FINDING, severity="high"), colour=True)
        medium = render_finding.render(FINDING, colour=True)

        self.assertIn("\x1b[31m▐", high)
        self.assertIn("\x1b[33m▐", medium)

    def test_colour_honours_no_color_and_the_override(self) -> None:
        self.assertTrue(render_finding.use_colour({}))
        self.assertFalse(render_finding.use_colour({"NO_COLOR": "1"}))
        self.assertFalse(render_finding.use_colour({"STACKTRACE_COLOR": "never"}))
        self.assertTrue(render_finding.use_colour({"NO_COLOR": "1", "STACKTRACE_COLOR": "always"}))


class QueryTests(unittest.TestCase):
    def test_absent_cli_is_silent(self) -> None:
        self.assertIsNone(render_finding.query("s", find_executable=lambda _: None))

    def test_query_asks_only_for_this_session_and_forwards_nothing_else(self) -> None:
        seen: dict[str, object] = {}

        def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            seen["argv"] = argv
            seen["kwargs"] = kwargs
            return completed({"finding": FINDING})

        render_finding.query("session-1", find_executable=lambda _: "/usr/bin/stacktrace", run=run)

        self.assertEqual(
            seen["argv"],
            ["/usr/bin/stacktrace", "notify", "next", "--session", "session-1", "--format", "json"],
        )
        self.assertEqual(seen["kwargs"]["timeout"], render_finding.QUERY_TIMEOUT_SECONDS)
        self.assertEqual(seen["kwargs"]["stdin"], subprocess.DEVNULL)

    def test_failure_modes_never_render(self) -> None:
        cases = {
            "non-zero exit": completed({"finding": FINDING}, code=1),
            "not json": subprocess.CompletedProcess(args=[], returncode=0, stdout=b"<html>", stderr=b""),
            "no finding": completed({"finding": None}),
            "missing field": completed({"finding": {k: v for k, v in FINDING.items() if k != "title"}}),
            "unknown severity": completed({"finding": dict(FINDING, severity="catastrophic")}),
        }
        for label, response in cases.items():
            with self.subTest(label):
                found = render_finding.query(
                    "s", find_executable=lambda _: "/usr/bin/stacktrace", run=lambda *a, **k: response
                )
                self.assertIsNone(found)

    def test_timeout_is_silent(self) -> None:
        def run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
            raise subprocess.TimeoutExpired(cmd="stacktrace", timeout=2.0)

        self.assertIsNone(
            render_finding.query("s", find_executable=lambda _: "/usr/bin/stacktrace", run=run)
        )


if __name__ == "__main__":
    unittest.main()
