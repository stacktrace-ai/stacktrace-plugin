from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PluginContractTests(unittest.TestCase):
    """Everything here except the CLI-gate test itself runs with a stub
    `stacktrace` on PATH: the hook now refuses to show the welcome without
    one, and these tests are about the marker and screen, not that gate."""

    _bindir: tempfile.TemporaryDirectory[str]
    _tooldirs: list[str] = []

    @classmethod
    def setUpClass(cls) -> None:
        cls._bindir = tempfile.TemporaryDirectory()
        stub = Path(cls._bindir.name, "stacktrace")
        stub.write_text("#!/bin/sh\nexit 0\n")
        stub.chmod(0o755)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._bindir.cleanup()
        for tools in cls._tooldirs:
            shutil.rmtree(tools, ignore_errors=True)

    def test_validator_accepts_the_repository(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_plugin.py")],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "plugin scaffold ok\n")

    @classmethod
    def _path_without_stacktrace(cls) -> str:
        """A PATH holding only what the hook needs and no `stacktrace`. Built
        from symlinks into a scratch directory rather than by filtering the
        host's PATH: filtering removes whole directories, and on a host where
        `stacktrace` was installed beside `sh` (Debian's `/usr/local/bin`, a
        container's `/bin`) that took `sh` with it and the test errored for a
        reason that had nothing to do with the gate."""
        tools = tempfile.mkdtemp(prefix="stacktrace-plugin-tools-")
        cls._tooldirs.append(tools)
        for name in ("sh", "awk", "mkdir", "dirname"):
            found = shutil.which(name)
            assert found, f"{name} not on PATH"
            os.symlink(found, os.path.join(tools, name))
        return tools

    @classmethod
    def _environment(cls, home: str, *, no_stacktrace: bool = False) -> dict[str, str]:
        """HOME is always the scratch directory, and NO_COLOR is never
        inherited from whatever shell is running the suite: a developer or
        CI image with it set would otherwise silently change what these
        tests see."""
        path = cls._path_without_stacktrace() if no_stacktrace else f"{cls._bindir.name}:{os.environ['PATH']}"
        environment = dict(os.environ, HOME=home, PATH=path)
        environment.pop("CLAUDE_CONFIG_DIR", None)
        environment.pop("NO_COLOR", None)
        return environment

    @classmethod
    def _session_start(cls, home: str) -> subprocess.CompletedProcess[str]:
        """Always with a scratch HOME. The hook writes a marker there, and a
        test that used the real one would silently consume the developer's own
        first-run welcome."""
        return subprocess.run(
            ["sh", str(ROOT / "scripts" / "session_start.sh")],
            check=True,
            capture_output=True,
            text=True,
            input='{"untrusted":"input"}',
            env=cls._environment(home),
        )

    def test_session_start_emits_only_the_notification_contract(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            self._session_start(home)  # consume the one-time welcome
            result = self._session_start(home)
        document = json.loads(result.stdout)
        output = document["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "SessionStart")
        context = output["additionalContext"]
        self.assertIn("STACKTRACE_NOTIFY_V1", context)
        self.assertIn("PushNotification", context)
        self.assertNotIn("untrusted", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_the_welcome_is_offered_once_per_installation(self) -> None:
        """Telemetry is on before anyone opens the screen, so the disclosure
        has to find the user. Once, not every session: a banner on the first
        prompt of the day is the thing people disable."""
        with tempfile.TemporaryDirectory() as home:
            first = json.loads(self._session_start(home).stdout)
            second = json.loads(self._session_start(home).stdout)

        self.assertIn("DETECTION POLICIES", first["systemMessage"])
        self.assertNotIn("systemMessage", second)
        for document in (first, second):
            context = document["hookSpecificOutput"]["additionalContext"]
            self.assertIn("STACKTRACE_NOTIFY_V1", context)

    def test_the_startup_screen_is_the_skill_screen_without_the_question(self) -> None:
        """One copy of the screen, read out of the skill. A startup message
        cannot take an answer, so the option cursor becomes the off command
        and every other line is the skill's, in order."""
        with tempfile.TemporaryDirectory() as home:
            shown = json.loads(self._session_start(home).stdout)["systemMessage"]
        skill = (ROOT / "skills" / "welcome" / "SKILL.md").read_text(encoding="utf-8")
        expected = [
            line
            for line in WelcomeScreenTests._screen(skill).split("\n")
            if not line.startswith(("  > Keep it on", "    Turn it off"))
        ]

        self.assertNotIn("Keep it on", shown)
        self.assertIn("stacktrace telemetry off", shown)
        self.assertEqual(
            [line for line in shown.split("\n") if "Turn it off at any time" not in line],
            expected,
        )

    def test_the_model_is_never_asked_to_run_the_welcome(self) -> None:
        """The skill sets `disable-model-invocation: true`, so an instruction
        to run it is one the model cannot follow. The first version gave that
        instruction, and the welcome never appeared."""
        with tempfile.TemporaryDirectory() as home:
            context = json.loads(self._session_start(home).stdout)["hookSpecificOutput"][
                "additionalContext"
            ]

        self.assertNotIn("/stacktrace:welcome", context)

    def test_the_welcome_waits_for_the_cli(self) -> None:
        """The skill's own step 1 refuses to print the screen before the CLI
        exists, because every claim on it is about a program that has to
        already run. The hook has to refuse too, and it must not spend the
        one-time marker on a screen it never showed."""
        with tempfile.TemporaryDirectory() as home:
            before = json.loads(
                subprocess.run(
                    ["sh", str(ROOT / "scripts" / "session_start.sh")],
                    check=True,
                    capture_output=True,
                    text=True,
                    input='{"untrusted":"input"}',
                    env=self._environment(home, no_stacktrace=True),
                ).stdout
            )
            self.assertNotIn("systemMessage", before)
            self.assertFalse(Path(home, ".claude", "stacktrace-welcomed").exists())

            after = json.loads(self._session_start(home).stdout)

        self.assertIn("DETECTION POLICIES", after["systemMessage"])

    def test_no_color_replaces_the_wordmark_with_the_word(self) -> None:
        """The skill tells whoever prints the screen to swap the wordmark for
        the word under NO_COLOR, but the hook shows the screen without a model
        in the loop to read that instruction, so it has to do the swap itself."""
        with tempfile.TemporaryDirectory() as home:
            environment = self._environment(home)
            environment["NO_COLOR"] = "1"
            result = subprocess.run(
                ["sh", str(ROOT / "scripts" / "session_start.sh")],
                check=True,
                capture_output=True,
                text=True,
                input='{"untrusted":"input"}',
                env=environment,
            )
        shown = json.loads(result.stdout)["systemMessage"]

        self.assertIn("STACKTRACE", shown.split("\n")[0])
        for glyph in "┌└├┴┬┤":
            self.assertNotIn(glyph, shown)
        self.assertIn("DETECTION POLICIES", shown)

    def test_an_unwritable_marker_costs_the_welcome_and_not_the_session(self) -> None:
        """The contract is the hook's job; the welcome is a bonus. A home the
        marker cannot be written under must not take the monitor down with it.

        The unwritable place is a path *through a regular file*, so `mkdir -p`
        fails with ENOTDIR for every user. A read-only directory does not do
        that: root writes through `chmod 500`, and the suite runs as root in
        most containers."""
        with tempfile.TemporaryDirectory() as home:
            blocker = Path(home, "not-a-directory")
            blocker.write_text("")
            environment = self._environment(home)
            environment["CLAUDE_CONFIG_DIR"] = str(blocker / "claude")
            result = subprocess.run(
                ["sh", str(ROOT / "scripts" / "session_start.sh")],
                check=True,
                capture_output=True,
                text=True,
                input='{"untrusted":"input"}',
                env=environment,
            )

        document = json.loads(result.stdout)
        self.assertIn("STACKTRACE_NOTIFY_V1", document["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("systemMessage", document)

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
