"""Every host runs one session start script, which logs each failure (ADR-0013)."""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_plugin import Stubs, isolated

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("claude-code", "codex", "cursor", "devin")
LINE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ (claude-code|codex|cursor|devin) plugin [a-z-]+( [A-Z0-9_.a-z]+)?$")
SECRET = "hook-input-secret"


def session_start_hooks() -> dict[str, dict[str, object]]:
    """Each kind's SessionStart handler, read from the file its host loads."""
    claude = json.loads((ROOT / "hooks/hooks.json").read_text())["hooks"]["SessionStart"]
    codex = json.loads((ROOT / "hooks/codex.json").read_text())["hooks"]["SessionStart"]
    cursor = json.loads((ROOT / "hooks/cursor.json").read_text())["hooks"]["sessionStart"]
    devin = json.loads((ROOT / "devin/hooks.json").read_text())["SessionStart"]
    return {
        "claude-code": claude[0]["hooks"][0],
        "codex": codex[0]["hooks"][0],
        "cursor": cursor[0],
        "devin": devin[0]["hooks"][0],
    }


class HookDeclarationTests(unittest.TestCase):
    def test_every_host_runs_the_one_script_for_fifteen_seconds(self) -> None:
        hooks = session_start_hooks()
        self.assertEqual(set(hooks), set(KINDS))
        for kind, handler in hooks.items():
            with self.subTest(kind=kind):
                self.assertIn(f"scripts/session_start.sh{'' if kind == 'cursor' else chr(34)} --agent-kind {kind}", handler["command"])
                self.assertNotIn("policy_hook.sh", handler["command"])
                self.assertEqual(handler["timeout"], 15)

    def test_devin_runs_a_byte_copy(self) -> None:
        copy = ROOT / "devin/scripts/session_start.sh"
        self.assertEqual(copy.read_bytes(), (ROOT / "scripts/session_start.sh").read_bytes())


class SessionStartLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stubs = Stubs()
        self.home = tempfile.TemporaryDirectory()
        marker = Path(self.home.name, ".claude", "stacktrace-welcomed")
        marker.parent.mkdir()
        marker.write_text("")  # already welcomed: these tests are about failures
        self.log = Path(self.home.name, ".local/state/stacktrace/session-start.log")

    def tearDown(self) -> None:
        self.stubs.cleanup()
        self.home.cleanup()

    def stub(self, register: str = "exit 0", version: str = "stacktrace 0.5.2 (openaca 0.7.0)") -> None:
        """A CLI whose `register` runs `register` and whose output and errors
        carry a secret, so a test can prove neither reaches the log."""
        (self.stubs.cli / "stacktrace").write_text(
            "#!/bin/sh\n"
            'case "$1" in\n'
            f'  --version) echo "{version} {SECRET}" ;;\n'
            "  telemetry) echo off ;;\n"
            f"  remote) cat >/dev/null; echo {SECRET}; echo {SECRET} >&2; {register} ;;\n"
            "esac\n"
        )

    def run_kind(self, kind: str, script: Path = ROOT / "scripts/session_start.sh", **options: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["sh", str(script), "--agent-kind", kind],
            input=json.dumps({"hook_event_name": "SessionStart", "prompt": SECRET}),
            capture_output=True, text=True, check=False,
            env=isolated(self.home.name, self.stubs, **options),
        )

    def lines(self) -> list[str]:
        return self.log.read_text().splitlines() if self.log.exists() else []

    def stages(self) -> list[str]:
        return [line.split(" ", 3)[3] for line in self.lines()]

    def assert_quiet_unless_claude_or_codex(self, kind: str, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        if kind in ("cursor", "devin"):
            self.assertEqual(result.stdout, "")

    def test_a_healthy_session_writes_nothing_and_prints_nothing_outside_claude(self) -> None:
        self.stub()
        for kind in KINDS:
            with self.subTest(kind=kind):
                result = self.run_kind(kind)
                self.assertEqual(result.returncode, 0)
                if kind == "claude-code":
                    self.assertIn("hookSpecificOutput", json.loads(result.stdout))
                else:
                    self.assertEqual(result.stdout, "")
        self.assertFalse(self.log.parent.exists())

    def test_each_failure_writes_its_stage_for_every_kind(self) -> None:
        cases = (
            ("cli-missing", {"cli": False}, {}),
            ("register-exit 2", {}, {"register": "exit 2"}),
            ("register-exit 1", {}, {"register": "exit 1"}),
            ("register-timeout", {"STACKTRACE_ADAPTER_CALL_TIMEOUT": "1"}, {"register": "sleep 30"}),
            ("cli-too-old 0.5.1", {"daemon": False}, {"version": "stacktrace 0.5.1"}),
            ("cli-too-old unreadable", {"daemon": False}, {"version": "stacktrace 0.5.2rc1"}),
            ("daemon-unreachable", {"daemon": False}, {}),
        )
        for stage, options, stub in cases:
            for kind in KINDS:
                with self.subTest(stage=stage, kind=kind):
                    self.log.unlink(missing_ok=True)
                    self.stub(**stub)
                    result = self.run_kind(kind, **options)
                    self.assert_quiet_unless_claude_or_codex(kind, result)
                    self.assertEqual(self.stages(), [stage])
                    (line,) = self.lines()
                    self.assertRegex(line, LINE)
                    self.assertEqual(line.split(" ")[1:3], [kind, "plugin"])

    def test_only_claude_checks_the_variables_that_stop_its_monitor(self) -> None:
        self.stub()
        for variable in ("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "DISABLE_TELEMETRY"):
            for kind in KINDS:
                with self.subTest(variable=variable, kind=kind):
                    self.log.unlink(missing_ok=True)
                    self.run_kind(kind, **{variable: SECRET})
                    expected = [f"monitor-disabled {variable}"] if kind == "claude-code" else []
                    self.assertEqual(self.stages(), expected)

    def test_hook_input_cli_output_and_environment_values_never_reach_the_log(self) -> None:
        self.stub(register="exit 3", version=f"stacktrace 0.5.1+{SECRET}")
        for kind in KINDS:
            self.run_kind(kind, daemon=False, DISABLE_TELEMETRY=SECRET)
        self.assertTrue(self.lines())
        self.assertNotIn(SECRET, self.log.read_text())
        for line in self.lines():
            self.assertRegex(line, LINE)

    def test_codex_shows_the_warnings_without_the_claude_skill(self) -> None:
        """Codex surfaces a SessionStart `systemMessage` as a warning."""
        self.stub()
        result = self.run_kind("codex", daemon=False)
        self.assertEqual(json.loads(result.stdout), {"systemMessage": "The Stacktrace daemon is not reachable."})
        result = self.run_kind("codex", cli=False)
        self.assertEqual(json.loads(result.stdout), {"systemMessage": "The Stacktrace CLI is not on PATH."})

    def test_the_log_is_private(self) -> None:
        self.stub(register="exit 1")
        self.run_kind("codex")
        self.assertEqual(stat.S_IMODE(self.log.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.log.stat().st_mode), 0o600)

    def test_the_state_directory_variable_moves_the_log(self) -> None:
        self.stub(register="exit 1")
        with tempfile.TemporaryDirectory() as state:
            self.run_kind("devin", STACKTRACE_STATE_DIR=str(Path(state, "s")))
            self.assertEqual(len(Path(state, "s", "session-start.log").read_text().splitlines()), 1)
        self.assertFalse(self.log.exists())

    def test_the_log_keeps_the_last_five_hundred_lines(self) -> None:
        self.stub(register="exit 1")
        self.log.parent.mkdir(parents=True)
        self.log.write_text("".join(f"2026-01-01T00:00:00Z codex cli old {n}\n" for n in range(600)))
        self.run_kind("cursor")
        lines = self.lines()
        self.assertEqual(len(lines), 500)
        self.assertEqual(lines[0], "2026-01-01T00:00:00Z codex cli old 101")
        self.assertTrue(lines[-1].endswith(" cursor plugin register-exit 1"))
        self.assertEqual(list(self.log.parent.iterdir()), [self.log])

    def test_a_failed_log_write_changes_nothing_else(self) -> None:
        """The state directory is a path through a regular file, so it
        cannot be created even by root."""
        self.stub(register="exit 1")
        blocker = Path(self.home.name, "not-a-directory")
        blocker.write_text("")
        options = {"daemon": False, "STACKTRACE_STATE_DIR": str(blocker / "state")}
        expected = self.run_kind("claude-code", daemon=False)
        result = self.run_kind("claude-code", **options)
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(json.loads(result.stdout), json.loads(expected.stdout))
        self.assertIn("The Stacktrace daemon is not reachable.", json.loads(result.stdout)["systemMessage"])

    def test_the_devin_copy_runs_from_its_own_folder(self) -> None:
        self.stub(register="exit 2")
        result = self.run_kind("devin", script=ROOT / "devin/scripts/session_start.sh")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertEqual(self.stages(), ["register-exit 2"])

    def test_an_unknown_kind_does_nothing(self) -> None:
        self.stub(register="exit 1")
        for arguments in ([], ["--agent-kind"], ["--agent-kind", "other"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    ["sh", str(ROOT / "scripts/session_start.sh"), *arguments],
                    input="{}", capture_output=True, text=True, check=False,
                    env=isolated(self.home.name, self.stubs),
                )
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
