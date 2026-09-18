from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import detect_and_notify as detector  # noqa: E402


def transcript(*entries: tuple[str, str, bool], command: str = "pytest") -> Path:
    """Write a transcript whose tool calls are (id, tool, failed) in order."""
    lines: list[str] = []
    for call_id, tool, _failed in entries:
        lines.append(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": call_id,
                                "name": tool,
                                "input": {"command": command},
                            }
                        ]
                    },
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
        call = {"command": "pytest"}
        first = detector.signature("Bash", call, "failed after 1.2s at /tmp/run-8471/test.py")
        second = detector.signature("Bash", call, "failed after 9.8s at /tmp/run-2290/test.py")

        self.assertEqual(first, second)

    def test_changing_assertion_values_are_not_one_streak(self) -> None:
        """A bare number can be the diagnostic itself -- an assertion's
        expected/actual value -- not volatile noise; erasing every digit
        hides three genuinely different failures behind one signature."""
        call = {"command": "pytest"}
        self.assertNotEqual(
            detector.signature("Bash", call, "AssertionError: expected 1, got 2"),
            detector.signature("Bash", call, "AssertionError: expected 2, got 3"),
        )

    def test_changing_values_sharing_a_time_unit_are_not_one_streak(self) -> None:
        """A value that happens to carry a time-unit suffix (`1ms`) can still
        be the diagnostic itself; only a recognised timing phrase (`after
        1.2s`) is volatile, not any number next to a unit-like word."""
        call = {"command": "pytest"}
        self.assertNotEqual(
            detector.signature("Bash", call, "expected 1ms, got 2ms"),
            detector.signature("Bash", call, "expected 2ms, got 3ms"),
        )

    def test_changing_source_paths_are_not_one_streak(self) -> None:
        """A source path like `/repo/a.py` is usually the diagnostic itself --
        which file failed -- not a volatile detail; only a known temp
        location folds."""
        call = {"command": "pytest"}
        self.assertNotEqual(
            detector.signature("Bash", call, "FAILED /repo/a.py"),
            detector.signature("Bash", call, "FAILED /repo/b.py"),
        )

    def test_changing_diagnostic_case_is_not_one_streak(self) -> None:
        """Case can be the value being diagnosed, not incidental formatting;
        folding it away must not collapse three different diagnoses."""
        call = {"command": "pytest"}
        self.assertNotEqual(
            detector.signature("Bash", call, "expected 'FOO', got 'foo'"),
            detector.signature("Bash", call, "expected 'Foo', got 'foo'"),
        )

    def test_short_hex_values_are_not_one_streak(self) -> None:
        """A short hex literal (`0x1`) is likelier a diagnosed value than a
        pointer; only address-like hex (long enough to plausibly be one)
        folds."""
        call = {"command": "pytest"}
        self.assertNotEqual(
            detector.signature("Bash", call, "expected 0x1, got 0x2"),
            detector.signature("Bash", call, "expected 0x2, got 0x3"),
        )

    def test_address_like_hex_still_folds(self) -> None:
        """A long hex value (a pointer, a memory address) is exactly the
        volatile-per-run noise the fold exists for."""
        call = {"command": "pytest"}
        self.assertEqual(
            detector.signature("Bash", call, "segfault at 0x7f8a1b2c3d40"),
            detector.signature("Bash", call, "segfault at 0x7f8a1b2c9999"),
        )

    def test_different_tools_are_different_failures(self) -> None:
        self.assertNotEqual(
            detector.signature("Bash", {}, "boom"), detector.signature("Edit", {}, "boom")
        )

    def test_different_commands_sharing_an_error_are_not_one_streak(self) -> None:
        """`Exit code 1` opens every failed Bash result; the call must disambiguate."""
        self.assertNotEqual(
            detector.signature("Bash", {"command": "pytest"}, "Exit code 1"),
            detector.signature("Bash", {"command": "npm run build"}, "Exit code 1"),
        )

    def test_different_call_arguments_are_not_one_streak(self) -> None:
        """A path or number in the call is what tells two calls apart; the
        error-normalisation noise must not erase it from the call side too."""
        self.assertNotEqual(
            detector.signature("Bash", {"command": "pytest /repo/a.py"}, "Exit code 1"),
            detector.signature("Bash", {"command": "pytest /repo/b.py"}, "Exit code 1"),
        )

    def test_different_diagnostics_sharing_a_status_line_are_not_one_streak(self) -> None:
        """The same command failing for different reasons behind the same
        generic status line must not look like the same failure."""
        self.assertNotEqual(
            detector.signature("Bash", {"command": "pytest"}, "Exit code 1\nAssertionError: test_foo failed"),
            detector.signature("Bash", {"command": "pytest"}, "Exit code 1\nAssertionError: test_bar failed"),
        )

    def test_call_case_and_whitespace_are_significant(self) -> None:
        """A case-sensitive filename, or meaningful spacing inside quoted call
        data, can be the only thing distinguishing two different calls."""
        self.assertNotEqual(
            detector.signature("Bash", {"command": "pytest Foo.py"}, "Exit code 1"),
            detector.signature("Bash", {"command": "pytest foo.py"}, "Exit code 1"),
        )

    def test_call_arguments_beyond_the_slice_limit_still_disambiguate(self) -> None:
        """A long shared setup prefix must not let a truncated identity key
        collide two calls that differ only after the truncation point."""
        prefix = "FOO=1 BAR=2 " * 20
        self.assertNotEqual(
            detector.signature("Bash", {"command": prefix + "target-a"}, "Exit code 1"),
            detector.signature("Bash", {"command": prefix + "target-b"}, "Exit code 1"),
        )

    def test_diagnostic_body_beyond_the_slice_limit_still_disambiguates(self) -> None:
        shared_prefix = "Exit code 1\n" + "stack frame line\n" * 40
        self.assertNotEqual(
            detector.signature("Bash", {"command": "pytest"}, shared_prefix + "AssertionError: test_foo"),
            detector.signature("Bash", {"command": "pytest"}, shared_prefix + "AssertionError: test_bar"),
        )


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

    def test_a_truthy_non_dict_message_is_ignored_not_crashed_on(self) -> None:
        """A synchronous hook must fail silent on a malformed record, not raise."""
        handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        handle.write(json.dumps({"type": "user", "message": ["not", "a", "dict"]}) + "\n")
        handle.close()

        self.assertEqual(detector.read_attempts(Path(handle.name)), [])

    def test_a_parallel_batch_is_one_occasion_not_several(self) -> None:
        """Three tool_use blocks issued together in one message, failing
        identically in one shared result message, is one occasion -- the
        agent had no chance to see any of them fail before issuing the
        others, so it isn't a retry loop of three."""
        handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        handle.write(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "id": cid, "name": "Bash", "input": {"command": "pytest"}}
                            for cid in ("a", "b", "c")
                        ]
                    },
                }
            )
            + "\n"
        )
        handle.write(
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": cid,
                                "is_error": "True",
                                "content": "Exit code 1",
                            }
                            for cid in ("a", "b", "c")
                        ]
                    },
                }
            )
            + "\n"
        )
        handle.close()

        attempts = detector.read_attempts(Path(handle.name))
        self.assertEqual(len(attempts), 1)

    def test_sequential_batches_still_reach_the_threshold(self) -> None:
        """Collapsing a batch to one occasion must not stop three genuinely
        sequential occasions -- each itself a batch -- from being counted."""

        def batch_lines(n: int) -> list[str]:
            ids = [f"{n}-{i}" for i in range(2)]
            lines = [
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {"type": "tool_use", "id": cid, "name": "Bash", "input": {"command": "pytest"}}
                                for cid in ids
                            ]
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": cid,
                                    "is_error": "True",
                                    "content": "Exit code 1",
                                }
                                for cid in ids
                            ]
                        },
                    }
                ),
            ]
            return lines

        lines = [line for n in range(3) for line in batch_lines(n)]
        handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        handle.write("\n".join(lines) + "\n")
        handle.close()

        attempts = detector.read_attempts(Path(handle.name))
        self.assertEqual(detector.streak(attempts), (3, "Bash"))


class TruncationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tail_bytes = detector.TAIL_BYTES
        self._max_resolve_bytes = detector.MAX_RESOLVE_BYTES

    def tearDown(self) -> None:
        detector.TAIL_BYTES = self._tail_bytes
        detector.MAX_RESOLVE_BYTES = self._max_resolve_bytes

    def test_untruncated_file_is_not_truncated(self) -> None:
        path = transcript(("a", "Bash", True))
        self.assertFalse(detector.is_truncated(path))

    def test_file_larger_than_the_window_is_truncated(self) -> None:
        detector.TAIL_BYTES = 10
        path = transcript(("a", "Bash", True))
        self.assertTrue(detector.is_truncated(path))

    def test_streak_touching_a_truncated_window_does_not_refire(self) -> None:
        """Six identical failures, but the window is shrunk to fit only the last
        three complete attempts. Without truncation-awareness this reports a
        fresh exact-threshold streak of 3 -- re-firing an alert that already
        fired for real attempt 3, defeating fire-once and turning it into
        wallpaper."""
        big = "X" * 900
        lines: list[str] = []
        for n in range(6):
            call_id = str(n)
            lines.append(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": call_id,
                                    "name": "Bash",
                                    "input": {"command": "pytest"},
                                }
                            ]
                        },
                    }
                )
            )
            lines.append(
                json.dumps(
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": call_id,
                                    "is_error": "True",
                                    "content": "Exit code 1\n" + big,
                                }
                            ]
                        },
                    }
                )
            )
        handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        handle.write("\n".join(lines) + "\n")
        handle.close()
        path = Path(handle.name)

        pair_len = len(lines[-1]) + len(lines[-2]) + 2
        detector.TAIL_BYTES = pair_len * 3 + 50  # room for exactly the last 3 pairs

        attempts = detector.read_attempts(path)
        self.assertEqual(detector.streak(attempts), (3, "Bash"))
        self.assertTrue(detector.is_truncated(path))

        import io

        stdin, stdout = sys.stdin, sys.stdout
        sys.stdin = io.StringIO(
            json.dumps({"hook_event_name": "PostToolUseFailure", "transcript_path": str(path)})
        )
        sys.stdout = io.StringIO()
        try:
            detector.main()
            output = sys.stdout.getvalue()
        finally:
            sys.stdin, sys.stdout = stdin, stdout

        self.assertEqual(output, "")

    def test_truncated_orphan_before_the_streak_does_not_refire(self) -> None:
        """The window can cut cleanly between a call's `tool_use` line and its
        `tool_result` line, leaving an orphan ("?") result ahead of a real
        3-streak. len(attempts) is then 4 while the streak is 3, so the old
        touches-the-edge check missed this -- but the orphan is itself proof
        the window's start isn't a clean boundary, so it must not refire
        either."""
        big = "X" * 900
        lines: list[str] = []
        result_line_offsets: list[int] = []
        for n in range(6):
            call_id = str(n)
            lines.append(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": call_id,
                                    "name": "Bash",
                                    "input": {"command": "pytest"},
                                }
                            ]
                        },
                    }
                )
            )
            result_line_offsets.append(sum(len(line) + 1 for line in lines))
            lines.append(
                json.dumps(
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": call_id,
                                    "is_error": "True",
                                    "content": "Exit code 1\n" + big,
                                }
                            ]
                        },
                    }
                )
            )
        handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        handle.write("\n".join(lines) + "\n")
        handle.close()
        path = Path(handle.name)

        # Orphan call 2's tool_use: the window starts exactly at call 2's
        # tool_result line, keeping it (as an unknown "?" attempt) plus the
        # three complete, identical pairs (3, 4, 5) after it.
        start_offset = result_line_offsets[2]
        detector.TAIL_BYTES = path.stat().st_size - start_offset

        attempts = detector.read_attempts(path)
        self.assertEqual(len(attempts), 4)
        self.assertEqual(attempts[0][2], "?")
        self.assertEqual(detector.streak(attempts), (3, "Bash"))
        self.assertTrue(detector.is_truncated(path))

        import io

        stdin, stdout = sys.stdin, sys.stdout
        sys.stdin = io.StringIO(
            json.dumps({"hook_event_name": "PostToolUseFailure", "transcript_path": str(path)})
        )
        sys.stdout = io.StringIO()
        try:
            detector.main()
            output = sys.stdout.getvalue()
        finally:
            sys.stdin, sys.stdout = stdin, stdout

        self.assertEqual(output, "")

    def test_a_legitimate_streak_past_unrelated_preamble_still_fires(self) -> None:
        """A big file alone doesn't mean the streak's own history was cut off:
        a huge non-tool preamble can push the file past TAIL_BYTES while the
        streak that follows it is complete and untouched. The fast tail read
        can't tell the difference from real truncation, but a full read can
        -- and must not stay silent on a real finding just because the file
        happened to be long before it."""
        detector.TAIL_BYTES = 2000
        preamble = json.dumps(
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "X" * 3000}]}}
        )
        lines = [preamble]
        for n in range(3):
            call_id = str(n)
            lines.append(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": call_id,
                                    "name": "Bash",
                                    "input": {"command": "pytest"},
                                }
                            ]
                        },
                    }
                )
            )
            lines.append(
                json.dumps(
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": call_id,
                                    "is_error": "True",
                                    "content": "Exit code 1",
                                }
                            ]
                        },
                    }
                )
            )
        handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        handle.write("\n".join(lines) + "\n")
        handle.close()
        path = Path(handle.name)

        self.assertTrue(detector.is_truncated(path))
        # The fast tail window alone would call this ambiguous:
        fast_attempts = detector.read_attempts(path)
        self.assertEqual(detector.streak(fast_attempts), (3, "Bash"))
        self.assertEqual(len(fast_attempts), 3)

        import io

        stdin, stdout = sys.stdin, sys.stdout
        sys.stdin = io.StringIO(
            json.dumps({"hook_event_name": "PostToolUseFailure", "transcript_path": str(path)})
        )
        sys.stdout = io.StringIO()
        try:
            detector.main()
            output = sys.stdout.getvalue()
        finally:
            sys.stdin, sys.stdout = stdin, stdout

        self.assertIn("stacktrace-progress-stall", output)

    def test_full_read_still_suppresses_a_genuinely_ambiguous_boundary(self) -> None:
        """The fallback must not just always fire: if the full file shows an
        orphan (or Claude Code's own compaction already trimmed the file)
        right before the streak, it's still genuinely unknown and must stay
        silent."""
        big = "X" * 900
        lines: list[str] = []
        result_line_offsets: list[int] = []
        for n in range(6):
            call_id = str(n)
            lines.append(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": call_id,
                                    "name": "Bash",
                                    "input": {"command": "pytest"},
                                }
                            ]
                        },
                    }
                )
            )
            result_line_offsets.append(sum(len(line) + 1 for line in lines))
            lines.append(
                json.dumps(
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": call_id,
                                    "is_error": "True",
                                    "content": "Exit code 1\n" + big,
                                }
                            ]
                        },
                    }
                )
            )
        # Simulate compaction: the file on disk itself starts mid-conversation,
        # at call 2's tool_result, with no tail-window trickery involved.
        full_text = "\n".join(lines) + "\n"
        handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        handle.write(full_text[result_line_offsets[2] :])
        handle.close()
        path = Path(handle.name)
        file_size = path.stat().st_size

        # The file itself (not our windowing) starts mid-conversation, at call
        # 2's tool_result -- the fallback's wider read finds this same orphan
        # immediately before the streak. First confirm that directly:
        wide_attempts = detector.read_attempts(path, tail_bytes=detector.MAX_RESOLVE_BYTES)
        self.assertEqual(len(wide_attempts), 4)
        self.assertEqual(wide_attempts[0][2], "?")
        self.assertEqual(detector.streak(wide_attempts), (3, "Bash"))

        # Now force the fast path into the ambiguous branch with an ordinary
        # tail window smaller than the file; the fallback's own wider read
        # must reach the same conclusion and stay silent, not fire just
        # because the fast window's edge looked clean.
        detector.TAIL_BYTES = file_size - 5
        self.assertTrue(detector.is_truncated(path))

        import io

        stdin, stdout = sys.stdin, sys.stdout
        sys.stdin = io.StringIO(
            json.dumps({"hook_event_name": "PostToolUseFailure", "transcript_path": str(path)})
        )
        sys.stdout = io.StringIO()
        try:
            detector.main()
            output = sys.stdout.getvalue()
        finally:
            sys.stdin, sys.stdout = stdin, stdout

        self.assertEqual(output, "")

    def test_fallback_stays_bounded_and_suppresses_past_its_own_cap(self) -> None:
        """The wider second look must not become the same unbounded read it
        replaced: a preamble bigger than even MAX_RESOLVE_BYTES must still
        leave the boundary unresolved, and unresolved must mean silent, not
        an ever-larger read."""
        detector.TAIL_BYTES = 500
        detector.MAX_RESOLVE_BYTES = 3000
        preamble = json.dumps(
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "X" * 5000}]}}
        )
        lines = [preamble]
        for n in range(3):
            call_id = str(n)
            lines.append(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": call_id,
                                    "name": "Bash",
                                    "input": {"command": "pytest"},
                                }
                            ]
                        },
                    }
                )
            )
            lines.append(
                json.dumps(
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": call_id,
                                    "is_error": "True",
                                    "content": "Exit code 1",
                                }
                            ]
                        },
                    }
                )
            )
        handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        handle.write("\n".join(lines) + "\n")
        handle.close()
        path = Path(handle.name)

        self.assertTrue(detector.is_truncated(path))
        self.assertTrue(detector.is_cut_short(path, detector.MAX_RESOLVE_BYTES))

        import io

        stdin, stdout = sys.stdin, sys.stdout
        sys.stdin = io.StringIO(
            json.dumps({"hook_event_name": "PostToolUseFailure", "transcript_path": str(path)})
        )
        sys.stdout = io.StringIO()
        try:
            detector.main()
            output = sys.stdout.getvalue()
        finally:
            sys.stdin, sys.stdout = stdin, stdout

        self.assertEqual(output, "")


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
