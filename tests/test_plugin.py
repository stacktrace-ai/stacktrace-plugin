from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WELCOME = ROOT / "scripts" / "welcome.txt"


#: A current release, with usage metrics on, unless the STUB_* variables say
#: otherwise. Records every call in STUB_LOG, so a test can prove a healthy
#: session never started it.
STACKTRACE_STUB = """#!/bin/sh
[ -n "${STUB_LOG:-}" ] && echo "$*" >>"$STUB_LOG"
case "$1" in
  --version) echo "${STUB_VERSION:-stacktrace 0.4.0 (openaca 0.7.0)}" ;;
  telemetry) echo "${STUB_TELEMETRY:-on}" ;;
  daemon) exit "${STUB_DAEMON_EXIT:-0}" ;;
esac
exit 0
"""

#: Every external command the hook runs.
TOOLS = ("sh", "awk", "mkdir", "dirname", "sed", "tr", "id")


class Stubs:
    """A `stacktrace` stub on a PATH that holds nothing else but symlinks to
    `TOOLS`, and a real Unix socket standing in for a running daemon's.

    Never the host's PATH, filtered or not: filtering removes whole
    directories, and where `stacktrace` sits beside `sh` (Debian's
    `/usr/local/bin`, a container's `/bin`) it took `sh` with it."""

    def __init__(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        base = Path(self._dir.name)
        self.cli = base / "cli"
        self.tools = base / "tools"
        self.cli.mkdir()
        stub = self.cli / "stacktrace"
        stub.write_text(STACKTRACE_STUB)
        stub.chmod(0o755)
        self.tools.mkdir()
        for name in TOOLS:
            found = shutil.which(name)
            assert found, f"{name} not on PATH"
            (self.tools / name).symlink_to(found)
        # Bound and closed: the file stays a socket, which is all `[ -S ]` asks.
        self.socket = base / "d.sock"
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(self.socket))
        listener.close()
        self.no_socket = base / "absent.sock"

    def path(self, *, cli: bool = True) -> str:
        return os.pathsep.join([str(self.cli)] * cli + [str(self.tools)])

    def cleanup(self) -> None:
        self._dir.cleanup()


def isolated(home: str, stubs: Stubs, *, cli: bool = True, daemon: bool = True, **extra: str) -> dict[str, str]:
    """HOME is always the scratch directory, and nothing that changes what the
    hook does is inherited from whatever shell is running the suite."""
    environment = dict(
        os.environ,
        HOME=home,
        PATH=stubs.path(cli=cli),
        STACKTRACE_DAEMON_SOCKET=str(stubs.socket if daemon else stubs.no_socket),
    )
    for name in (
        "CLAUDE_CONFIG_DIR",
        "CLAUDE_PLUGIN_DATA",
        "CLAUDE_CODE_REMOTE",
        "NO_COLOR",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
        "DISABLE_TELEMETRY",
        "STUB_LOG",
        "STUB_VERSION",
        "STUB_TELEMETRY",
    ):
        environment.pop(name, None)
    environment.update(extra)
    return environment


def session_start(environment: dict[str, str]) -> dict[str, object]:
    result = subprocess.run(
        ["sh", str(ROOT / "scripts" / "session_start.sh")],
        check=True,
        capture_output=True,
        text=True,
        input='{"untrusted":"input"}',
        env=environment,
    )
    assert result.stderr == "", result.stderr
    return json.loads(result.stdout)


class PluginContractTests(unittest.TestCase):
    """Everything here except the CLI-gate test itself runs with a stub
    `stacktrace` on PATH and a daemon socket present: the hook refuses to show
    the welcome without the CLI, and these tests are about the marker and
    screen, not the diagnosis."""

    _stubs: Stubs

    @classmethod
    def setUpClass(cls) -> None:
        cls._stubs = Stubs()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._stubs.cleanup()

    def test_validator_accepts_the_repository(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_plugin.py")],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "plugin scaffold ok\n")

    def _run_validator_with_version(self, version: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="stacktrace-plugin-scaffold-") as scaffold:
            shutil.copytree(ROOT, scaffold, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
            manifest_path = Path(scaffold, ".claude-plugin", "plugin.json")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["version"] = version
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(Path(scaffold, "scripts", "validate_plugin.py"))],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_validator_rejects_leading_zeroes_in_version(self) -> None:
        for version in ("01.0.0", "1.02.3", "1.2.03"):
            with self.subTest(version=version):
                result = self._run_validator_with_version(version)
                self.assertEqual(result.returncode, 1)
                self.assertIn("semver version", result.stderr)

    def test_validator_rejects_non_ascii_digits(self) -> None:
        for version in ("1٢2.0.0", "0.1٠2.0", "0.1.٢"):
            with self.subTest(version=version):
                result = self._run_validator_with_version(version)
                self.assertEqual(result.returncode, 1)
                self.assertIn("semver version", result.stderr)

    def test_validator_accepts_compliant_versions(self) -> None:
        for version in ("0.1.0", "1.2.3", "10.20.30"):
            with self.subTest(version=version):
                result = self._run_validator_with_version(version)
                self.assertEqual(result.returncode, 0, result.stderr)

    @classmethod
    def _environment(cls, home: str, *, no_stacktrace: bool = False) -> dict[str, str]:
        return isolated(home, cls._stubs, cli=not no_stacktrace)

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

        self.assertIn("WHAT WE DETECT", first["systemMessage"])
        self.assertNotIn("systemMessage", second)
        for document in (first, second):
            context = document["hookSpecificOutput"]["additionalContext"]
            self.assertIn("STACKTRACE_NOTIFY_V1", context)

    def test_the_startup_screen_is_the_welcome_file(self) -> None:
        """One copy of the screen, shown line for line."""
        with tempfile.TemporaryDirectory() as home:
            shown = json.loads(self._session_start(home).stdout)["systemMessage"]

        self.assertEqual(shown, WELCOME.read_text(encoding="utf-8"))
        self.assertIn("stacktrace telemetry off", shown)

    def test_the_marker_lives_in_the_plugin_data_directory(self) -> None:
        """Claude Code deletes `CLAUDE_PLUGIN_DATA` when the plugin is
        uninstalled, so a reinstall welcomes again. A marker in the config
        directory survived every reinstall (ADR-0007)."""
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as data:
            environment = self._environment(home)
            environment["CLAUDE_PLUGIN_DATA"] = str(Path(data, "stacktrace-stacktrace"))

            def start() -> dict[str, object]:
                return json.loads(
                    subprocess.run(
                        ["sh", str(ROOT / "scripts" / "session_start.sh")],
                        check=True,
                        capture_output=True,
                        text=True,
                        input="{}",
                        env=environment,
                    ).stdout
                )

            first = start()
            self.assertTrue(Path(data, "stacktrace-stacktrace", "stacktrace-welcomed").exists())
            self.assertFalse(Path(home, ".claude", "stacktrace-welcomed").exists())
            second = start()

        self.assertIn("systemMessage", first)
        self.assertNotIn("systemMessage", second)

    def test_the_model_is_never_asked_to_run_the_welcome(self) -> None:
        """The first version asked the model to run a welcome skill it could
        not invoke, and the welcome never appeared. The screen goes to the
        user directly, and the model is told nothing about it."""
        with tempfile.TemporaryDirectory() as home:
            context = json.loads(self._session_start(home).stdout)["hookSpecificOutput"][
                "additionalContext"
            ]

        self.assertNotIn("WHAT WE DETECT", context)

    def test_the_welcome_waits_for_the_cli(self) -> None:
        """Every claim on the screen is about a program that has to already
        run, so the hook refuses to show it before the CLI exists, and must
        not spend the one-time marker on a screen it never showed."""
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
            self.assertNotIn("WHAT WE DETECT", before.get("systemMessage", ""))
            self.assertFalse(Path(home, ".claude", "stacktrace-welcomed").exists())

            after = json.loads(self._session_start(home).stdout)

        self.assertIn("WHAT WE DETECT", after["systemMessage"])

    def test_no_color_replaces_the_wordmark_with_the_word(self) -> None:
        """Under NO_COLOR the wordmark becomes the word."""
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
        self.assertIn("WHAT WE DETECT", shown)

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


class DiagnosisTests(unittest.TestCase):
    """What session start says is wrong (ADR-0008). One line per problem,
    nothing on a healthy machine, and never a fix applied."""

    def setUp(self) -> None:
        self.stubs = Stubs()
        self.home = tempfile.TemporaryDirectory()
        self.log = Path(self.home.name, "calls.log")
        marker = Path(self.home.name, ".claude", "stacktrace-welcomed")
        marker.parent.mkdir()
        marker.write_text("")  # already welcomed: these tests are about diagnosis

    def tearDown(self) -> None:
        self.stubs.cleanup()
        self.home.cleanup()

    def shown(self, **options: object) -> list[str]:
        document = session_start(isolated(self.home.name, self.stubs, STUB_LOG=str(self.log), **options))
        return str(document.get("systemMessage", "")).splitlines()

    def calls(self) -> list[str]:
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_a_healthy_session_says_nothing_and_starts_no_python(self) -> None:
        """The CLI check is `command -v` and the daemon check a socket test,
        so a working machine never pays for a Python start."""
        self.assertEqual(self.shown(), [])
        self.assertEqual(self.calls(), [])

    def test_a_missing_cli_is_named_with_its_install_command(self) -> None:
        self.assertEqual(
            self.shown(cli=False),
            [
                "The Stacktrace CLI is not installed. Install it with "
                "`uv tool install stacktrace-cli`, then run /reload-plugins."
            ],
        )

    def test_a_missing_daemon_socket_is_reported(self) -> None:
        self.assertEqual(
            self.shown(daemon=False), ["The Stacktrace daemon is not running. /stacktrace:status explains why."]
        )
        self.assertEqual(self.calls(), ["--version"])

    def test_a_cli_below_the_floor_is_the_likelier_cause_of_no_daemon(self) -> None:
        """0.4.0 is the first release with the daemon the monitor subscribes
        to. A build from source is held to the same floor."""
        for version in ("stacktrace 0.3.1 (openaca 0.6.0)", "stacktrace 0.3.1+abc1234 (openaca 0.6.0)"):
            with self.subTest(version=version):
                lines = self.shown(daemon=False, STUB_VERSION=version)

                self.assertEqual(len(lines), 1)
                self.assertIn("needs stacktrace 0.4.0 or newer", lines[0])
                self.assertIn(version, lines[0])

    def test_newer_versions_pass_the_floor(self) -> None:
        for version in ("stacktrace 0.4.0+0d20658 (openaca 0.7.0)", "stacktrace 0.10.0 (openaca 0.7.0)"):
            with self.subTest(version=version):
                self.assertEqual(
                    self.shown(daemon=False, STUB_VERSION=version),
                    ["The Stacktrace daemon is not running. /stacktrace:status explains why."],
                )

    def test_the_variables_that_stop_plugin_monitors_are_named(self) -> None:
        for variable in ("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "DISABLE_TELEMETRY"):
            with self.subTest(variable=variable):
                lines = self.shown(**{variable: "1"})

                self.assertEqual(len(lines), 1)
                self.assertTrue(lines[0].startswith(f"{variable} is set"))

    def test_diagnosis_changes_nothing(self) -> None:
        """Stateless: whatever it finds, HOME holds only what the test put
        there."""
        before = sorted(str(q) for q in Path(self.home.name).rglob("*"))
        for options in ({"cli": False}, {"daemon": False}, {"STUB_VERSION": "stacktrace 0.3.1 (x)"}):
            with self.subTest(options=options):
                self.shown(**options)
        after = sorted(str(q) for q in Path(self.home.name).rglob("*") if q != self.log)
        self.assertEqual(after, before)


class WelcomeStateTests(unittest.TestCase):
    """The welcome shows the telemetry state the CLI owns (ADR-0008)."""

    def setUp(self) -> None:
        self.stubs = Stubs()
        self.home = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.stubs.cleanup()
        self.home.cleanup()

    def welcome(self, **options: str) -> str:
        return str(session_start(isolated(self.home.name, self.stubs, **options)).get("systemMessage", ""))

    def test_metrics_on_shows_the_screen_as_written(self) -> None:
        self.assertEqual(self.welcome(), WELCOME.read_text(encoding="utf-8"))

    def test_metrics_off_drops_what_is_sent_and_the_off_switch(self) -> None:
        shown = self.welcome(STUB_TELEMETRY="off")

        self.assertIn("USAGE METRICS  (off)", shown)
        self.assertNotIn("Sent as it happens", shown)
        self.assertNotIn("stacktrace telemetry off", shown)
        self.assertIn("stacktrace telemetry show", shown)
        self.assertIn("Never sent", shown)
        self.assertNotIn("\n\n\n\n", shown)

    def test_an_unreadable_state_shows_the_fuller_disclosure(self) -> None:
        self.assertIn("USAGE METRICS  (on)", self.welcome(STUB_TELEMETRY="garbled"))

    def test_a_remote_session_ignores_the_marker(self) -> None:
        """Cloud sessions recreate plugin data, so the marker cannot be
        trusted there: the welcome shows whenever metrics are on, and the
        marker is neither read nor written."""
        remote = {"CLAUDE_CODE_REMOTE": "true"}
        first = self.welcome(**remote)
        second = self.welcome(**remote)

        self.assertIn("WHAT WE DETECT", first)
        self.assertIn("WHAT WE DETECT", second)
        self.assertFalse(Path(self.home.name, ".claude", "stacktrace-welcomed").exists())

    def test_a_remote_session_with_metrics_off_shows_nothing(self) -> None:
        self.assertEqual(self.welcome(CLAUDE_CODE_REMOTE="true", STUB_TELEMETRY="off"), "")


class WelcomeScreenTests(unittest.TestCase):
    """The screen is a claim, and it is written down twice."""

    @staticmethod
    def _screen(text: str) -> str:
        blocks = re.findall(r"```\n(.*?)```", text, re.S)
        matching = [block for block in blocks if "WHAT WE DETECT" in block]
        assert len(matching) == 1, f"expected one screen, found {len(matching)}"
        return matching[0]

    def test_the_welcome_is_the_screen_the_adr_specifies(self) -> None:
        """Two copies of the same screen drift, and the drift is invisible:
        the ADR is what review reads and the file is what a user sees."""
        adr = (
            ROOT / "docs" / "adrs"
            / "0007-show-the-welcome-once-at-start-and-forget-it-on-uninstall.md"
        ).read_text(encoding="utf-8")
        skill = WELCOME.read_text(encoding="utf-8")

        self.assertEqual(skill, self._screen(adr))

    def test_the_wordmark_rows_are_the_same_width(self) -> None:
        """Row two ends in a trailing space. Without it the `E` sits a column
        short, and every editor that strips trailing whitespace breaks it."""
        skill = WELCOME.read_text(encoding="utf-8")
        rows = [
            line for line in skill.split("\n")
            if any(glyph in line for glyph in "\u250c\u2514\u251c\u2534\u252c\u2524")
        ][:3]

        self.assertEqual(len(rows), 3)
        self.assertEqual({len(row) for row in rows}, {32})

    def test_the_screen_fits_an_eighty_column_terminal(self) -> None:
        skill = WELCOME.read_text(encoding="utf-8")
        too_wide = [line for line in skill.split("\n") if len(line) > 72]

        self.assertEqual(too_wide, [])

    def test_the_welcome_never_says_opt_in(self) -> None:
        """Usage metrics are on before the screen appears (stacktrace ADR-0039), so there
        is nothing to opt into and saying so would be untrue."""
        skill = WELCOME.read_text(encoding="utf-8")

        self.assertNotIn("opt in", skill.lower())


if __name__ == "__main__":
    unittest.main()
