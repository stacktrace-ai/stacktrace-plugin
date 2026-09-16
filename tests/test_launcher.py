from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "launch_auto_sync.py"
SPEC = importlib.util.spec_from_file_location("launch_auto_sync", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class RecordingInput:
    def __init__(self) -> None:
        self.value = b""
        self.closed = False

    def write(self, value: bytes) -> int:
        self.value += value
        return len(value)

    def close(self) -> None:
        self.closed = True


class RecordingProcess:
    def __init__(self) -> None:
        self.stdin = RecordingInput()


class LauncherTests(unittest.TestCase):
    def test_filter_forwards_only_required_metadata(self) -> None:
        source = {
            "session_id": "session-1",
            "transcript_path": "/tmp/session-1.jsonl",
            "cwd": "/tmp/project",
            "hook_event_name": "Stop",
            "last_assistant_message": "SECRET RESPONSE",
            "tool_input": {"token": "SECRET TOKEN"},
        }

        event = launcher.filtered_event(json.dumps(source))

        self.assertEqual(
            event,
            {
                "session_id": "session-1",
                "transcript_path": "/tmp/session-1.jsonl",
                "cwd": "/tmp/project",
                "hook_event_name": "Stop",
            },
        )
        self.assertNotIn("SECRET", json.dumps(event))

    def test_filter_rejects_invalid_or_unexpected_events(self) -> None:
        self.assertIsNone(launcher.filtered_event("not-json"))
        self.assertIsNone(launcher.filtered_event("[]"))
        self.assertIsNone(
            launcher.filtered_event(
                json.dumps(
                    {
                        "session_id": "session-1",
                        "transcript_path": "/tmp/session-1.jsonl",
                        "cwd": "/tmp/project",
                        "hook_event_name": "PreToolUse",
                    }
                )
            )
        )

    def test_launch_detaches_and_pipes_the_filtered_event(self) -> None:
        event = {
            "session_id": "session-1",
            "transcript_path": "/tmp/session-1.jsonl",
            "cwd": "/tmp/project",
            "hook_event_name": "SessionEnd",
        }
        recorded: dict[str, Any] = {}
        process = RecordingProcess()

        def popen(command: list[str], **options: Any) -> RecordingProcess:
            recorded["command"] = command
            recorded["options"] = options
            return process

        launched = launcher.launch(
            event,
            find_executable=lambda _: "/tools/stacktrace",
            popen=popen,
        )

        self.assertTrue(launched)
        self.assertEqual(
            recorded["command"],
            ["/tools/stacktrace", "remote", "auto-sync", "run"],
        )
        options = recorded["options"]
        self.assertEqual(options["stdin"], subprocess.PIPE)
        self.assertEqual(options["stdout"], subprocess.DEVNULL)
        self.assertEqual(options["stderr"], subprocess.DEVNULL)
        if sys.platform == "win32":
            self.assertIn("creationflags", options)
        else:
            self.assertIs(options["start_new_session"], True)
        self.assertEqual(json.loads(process.stdin.value), event)
        self.assertTrue(process.stdin.closed)

    def test_missing_stacktrace_is_a_clean_noop(self) -> None:
        self.assertFalse(
            launcher.launch(
                {
                    "session_id": "s",
                    "transcript_path": "/tmp/s.jsonl",
                    "cwd": "/tmp",
                    "hook_event_name": "Stop",
                },
                find_executable=lambda _: None,
                popen=lambda *_args, **_kwargs: self.fail("popen must not run"),
            )
        )

    def test_main_never_echoes_content_or_disrupts_claude(self) -> None:
        secret = "SECRET ASSISTANT RESPONSE"
        raw = json.dumps({"hook_event_name": "Stop", "last_assistant_message": secret})
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch.object(sys, "stdin", io.StringIO(raw)),
            patch.object(sys, "stdout", stdout),
            patch.object(sys, "stderr", stderr),
        ):
            self.assertEqual(launcher.main(), 0)

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
