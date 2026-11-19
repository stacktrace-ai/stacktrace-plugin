"""In a Cowork VM, session start installs the CLI and enrolls (ADR-0014), and
the journal-only events reach the CLI only without a transcript (stacktrace
ADR-0260)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_plugin import Stubs, isolated

ROOT = Path(__file__).resolve().parents[1]
#: A token in the shape of a real one, made up for these tests.
TOKEN = "stk_test_4f0c7a8e1b2c4d3e8f90"
PIN = "stacktrace-cli==0.26.0"

CLI = """#!/bin/sh
echo "cli $* token=${STACKTRACE_REMOTE_TOKEN:-none} api=${STACKTRACE_REMOTE_API_URL:-none}" >>"$STUB_LOG"
case "$1" in
  --version) echo "stacktrace 0.26.0 (openaca 0.15.0)" ;;
  telemetry) echo off ;;
  remote)
    case "$*" in
      *"hooks status"*) printf '{"desired_revision": %s}\n' "${STUB_REVISION:-87}" ;;
      *) cat >/dev/null ;;
    esac ;;
esac
exit 0
"""


class CoworkSessionStartTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stubs = Stubs()
        self.home = tempfile.TemporaryDirectory()
        self.plugin = tempfile.TemporaryDirectory()
        self.extra = tempfile.TemporaryDirectory()
        shutil.copytree(ROOT / "scripts", Path(self.plugin.name, "scripts"))
        self.log = Path(self.extra.name, "calls.log")
        self.log.write_text("")
        tools = Path(self.extra.name, "bin")
        tools.mkdir()
        for name in ("cat", "chmod", "grep", "rmdir", "find"):
            (tools / name).symlink_to(shutil.which(name))  # type: ignore[arg-type]
        self.tools = tools
        self.uv(install="ok")
        self.curl(exit_code=0)
        self.boot = "boot-a"

    def tearDown(self) -> None:
        for directory in (self.stubs, self.home, self.plugin, self.extra):
            directory.cleanup()

    def uv(self, install: str) -> None:
        """A `uv` that records its arguments and, on `ok`, installs the CLI stub."""
        body = (
            'mkdir -p "$HOME/.local/bin"\n'
            f"cat >\"$HOME/.local/bin/stacktrace\" <<'STUB'\n{CLI}STUB\n"
            'chmod 755 "$HOME/.local/bin/stacktrace"\n'
            if install == "ok"
            else "exit 1\n"
        )
        path = self.tools / "uv"
        path.write_text(f'#!/bin/sh\necho "uv $*" >>"$STUB_LOG"\n{body}')
        path.chmod(0o755)

    def curl(self, exit_code: int) -> None:
        path = self.tools / "curl"
        path.write_text(f'#!/bin/sh\necho "curl $*" >>"$STUB_LOG"\nexit {exit_code}\n')
        path.chmod(0o755)

    def enroll(self, text: str) -> None:
        folder = Path(self.plugin.name, "cowork")
        folder.mkdir(exist_ok=True)
        (folder / "enroll.env").write_text(text)

    def run_start(self, entrypoint: str = "remote_cowork") -> subprocess.CompletedProcess[str]:
        env = isolated(self.home.name, self.stubs, cli=False, daemon=True)
        env["PATH"] = os.pathsep.join([str(self.tools), env["PATH"]])
        env.update(
            CLAUDE_CODE_ENTRYPOINT=entrypoint,
            CLAUDE_CODE_REMOTE="true",
            STUB_LOG=str(self.log),
            STACKTRACE_BOOT_ID=self.boot,
        )
        return subprocess.run(
            ["sh", str(Path(self.plugin.name, "scripts/session_start.sh")), "--agent-kind", "claude-code"],
            input=json.dumps({"hook_event_name": "SessionStart", "source": "startup"}),
            capture_output=True, text=True, check=False, env=env,
        )

    def calls(self) -> list[str]:
        return self.log.read_text().splitlines()

    def ready(self) -> str:
        marker = Path(self.home.name, ".local/state/stacktrace/cowork-ready")
        return marker.read_text().strip() if marker.exists() else ""

    def run_hook(self, *args: str, payload: str = '{"hook_event_name":"UserPromptSubmit"}') -> subprocess.CompletedProcess[str]:
        env = isolated(self.home.name, self.stubs, cli=False, daemon=True)
        env["PATH"] = os.pathsep.join([str(self.tools), env["PATH"]])
        env.update(CLAUDE_CODE_ENTRYPOINT="remote_cowork", STUB_LOG=str(self.log), STACKTRACE_BOOT_ID=self.boot)
        return subprocess.run(
            ["sh", str(Path(self.plugin.name, "scripts/policy_hook.sh")), *args, "admit"],
            input=payload, capture_output=True, text=True, check=False, env=env,
        )

    def message(self, result: subprocess.CompletedProcess[str]) -> str:
        return str(json.loads(result.stdout).get("systemMessage", ""))

    def test_a_cowork_vm_installs_the_pinned_cli_and_registers_with_the_token(self) -> None:
        self.enroll(f"STACKTRACE_REMOTE_TOKEN={TOKEN}\n")

        result = self.run_start()

        self.assertEqual(result.returncode, 0)
        self.assertIn(f"uv tool install --quiet {PIN}", self.calls())
        register = [c for c in self.calls() if c.startswith("cli remote policy hooks register")]
        self.assertIn(f"cli remote policy hooks register --agent-kind claude-code token={TOKEN} api=none", register)
        self.assertNotIn("not connected", self.message(result))
        self.assertEqual(self.ready(), "boot-a")

    def test_the_wheel_the_zip_carries_is_installed_instead_of_the_pin(self) -> None:
        self.enroll(f"STACKTRACE_REMOTE_TOKEN={TOKEN}\nSTACKTRACE_CLI_WHEEL=stacktrace_cli-0.27.0-py3-none-any.whl\n")
        Path(self.plugin.name, "cowork/stacktrace_cli-0.27.0-py3-none-any.whl").write_text("")

        self.run_start()

        wheel = Path(self.plugin.name, "cowork/stacktrace_cli-0.27.0-py3-none-any.whl")
        self.assertIn(f"uv tool install --quiet {wheel}", self.calls())

    def test_a_wheel_name_with_a_path_is_ignored(self) -> None:
        self.enroll("STACKTRACE_CLI_WHEEL=../../etc/passwd\n")

        self.run_start()

        self.assertIn(f"uv tool install --quiet {PIN}", self.calls())

    def test_an_installed_cli_is_not_installed_again(self) -> None:
        self.uv(install="ok")
        self.run_start()
        first = [c for c in self.calls() if c.startswith("uv ")]
        self.log.write_text("")

        self.run_start()

        self.assertEqual(len(first), 1)
        self.assertEqual([c for c in self.calls() if c.startswith("uv ")], [])

    def test_only_the_known_names_with_plain_values_are_taken(self) -> None:
        self.enroll(
            "STACKTRACE_REMOTE_API_URL=https://api.example.net\n"
            "STACKTRACE_REMOTE_TOKEN=two words\n"
            "PATH=/tmp/evil\n"
        )

        self.run_start()

        register = [c for c in self.calls() if c.startswith("cli remote policy hooks register")]
        self.assertIn("cli remote policy hooks register --agent-kind claude-code token=none api=https://api.example.net", register)

    def test_a_failed_install_says_so_once_and_the_task_continues(self) -> None:
        self.uv(install="fail")

        result = self.run_start()

        self.assertEqual(result.returncode, 0)
        message = self.message(result)
        self.assertEqual(message.count("Stacktrace is not connected"), 1)
        self.assertIn("Organization settings > Capabilities > Code execution", message)
        self.assertNotIn("daemon", message)
        log = Path(self.home.name, ".local/state/stacktrace/session-start.log").read_text()
        self.assertIn("plugin cowork-install-failed", log)

    def test_an_api_that_does_not_answer_says_so(self) -> None:
        self.curl(exit_code=56)

        result = self.run_start()

        self.assertIn("api.stacktrace.ai", self.message(result))

    def test_the_first_prompt_waits_for_setup_before_it_is_judged(self) -> None:
        # Cowork runs the first prompt's hooks before SessionStart ends
        # (ADR-0014), so the deciding hook sets the VM up itself.
        self.enroll(f"STACKTRACE_REMOTE_TOKEN={TOKEN}\n")

        result = self.run_hook()

        self.assertEqual(result.returncode, 0)
        calls = self.calls()
        install = calls.index(f"uv tool install --quiet {PIN}")
        register = calls.index(f"cli remote policy hooks register --agent-kind claude-code token={TOKEN} api=none")
        admit = next(i for i, c in enumerate(calls) if c.startswith("cli remote policy hooks admit"))
        self.assertLess(install, register)
        self.assertLess(register, admit)
        self.assertEqual(self.ready(), "boot-a")

    def test_a_ready_boot_is_not_set_up_again(self) -> None:
        self.run_hook()
        self.log.write_text("")

        self.run_hook()

        self.assertEqual([c for c in self.calls() if "register" in c or c.startswith("uv ")], [])

    def test_a_restarted_vm_is_set_up_again(self) -> None:
        # A restart stops the daemon; the kernel's boot id changes with it.
        self.run_hook()
        self.log.write_text("")
        self.boot = "boot-b"

        self.run_hook()

        self.assertTrue(any(c.startswith("cli remote policy hooks register") for c in self.calls()))
        self.assertEqual([c for c in self.calls() if c.startswith("uv ")], [])
        self.assertEqual(self.ready(), "boot-b")

    def test_a_daemon_without_the_policy_is_not_ready(self) -> None:
        # A daemon that answers but holds no policy lets every action through.
        os.environ["STUB_REVISION"] = "null"
        os.environ["STACKTRACE_COWORK_POLICY_SECONDS"] = "2"
        self.addCleanup(os.environ.pop, "STUB_REVISION", None)
        self.addCleanup(os.environ.pop, "STACKTRACE_COWORK_POLICY_SECONDS", None)

        self.run_hook()

        self.assertEqual(self.ready(), "")
        failed = Path(self.home.name, ".local/state/stacktrace/cowork-failed").read_text().split()
        self.assertEqual(failed[:2], ["boot-a", "5"])

    def test_a_failed_setup_is_not_waited_on_again(self) -> None:
        self.uv(install="fail")
        self.run_hook()
        self.log.write_text("")

        self.run_hook()

        self.assertEqual([c for c in self.calls() if c.startswith("uv ")], [])

    def test_a_journal_only_hook_starts_setup_and_does_not_wait(self) -> None:
        slow = self.tools / "uv"
        slow.write_text('#!/bin/sh\nsleep 4\nexit 1\n')
        slow.chmod(0o755)
        import time

        started = time.monotonic()
        self.run_hook("--without-transcript", payload='{"hook_event_name":"Stop","transcript_path":""}')

        self.assertLess(time.monotonic() - started, 3)

    def test_outside_cowork_the_plugin_installs_nothing_and_reads_no_token(self) -> None:
        self.enroll(f"STACKTRACE_REMOTE_TOKEN={TOKEN}\n")

        self.run_start(entrypoint="cli")

        self.assertEqual([c for c in self.calls() if c.startswith(("uv ", "curl "))], [])


class WithoutTranscriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stubs = Stubs()
        self.home = tempfile.TemporaryDirectory()
        self.extra = tempfile.TemporaryDirectory()
        self.log = Path(self.extra.name, "calls.log")
        tools = Path(self.extra.name, "bin")
        tools.mkdir()
        (tools / "cat").symlink_to(shutil.which("cat"))  # type: ignore[arg-type]
        cli = tools / "stacktrace"
        cli.write_text('#!/bin/sh\necho "$* $(cat)" >>"$STUB_LOG"\necho \'{"decision":"block"}\'\n')
        cli.chmod(0o755)
        self.tools = tools

    def tearDown(self) -> None:
        for directory in (self.stubs, self.home, self.extra):
            directory.cleanup()

    def run_hook(self, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
        env = isolated(self.home.name, self.stubs, cli=False, STUB_LOG=str(self.log))
        env["PATH"] = os.pathsep.join([str(self.tools), env["PATH"]])
        return subprocess.run(
            ["sh", str(ROOT / "scripts/policy_hook.sh"), "--without-transcript", "admit"],
            input=json.dumps(payload), capture_output=True, text=True, check=False, env=env,
        )

    def test_a_hook_with_a_transcript_never_starts_the_cli(self) -> None:
        result = self.run_hook({"hook_event_name": "Stop", "transcript_path": "/root/.claude/projects/p/s.jsonl"})

        self.assertEqual((result.returncode, result.stdout), (0, ""))
        self.assertFalse(self.log.exists())

    def test_a_hook_without_a_transcript_reaches_admit_with_its_payload(self) -> None:
        payload = {"hook_event_name": "Stop", "transcript_path": "", "session_id": "s"}

        result = self.run_hook(payload)

        self.assertEqual(result.stdout, '{"decision":"block"}\n')
        self.assertEqual(self.log.read_text(), f"remote policy hooks admit {json.dumps(payload)}\n")

    def test_the_spaced_form_counts_as_no_transcript(self) -> None:
        result = self.run_hook({"transcript_path": "", "hook_event_name": "Stop"})

        self.assertEqual(result.stdout, '{"decision":"block"}\n')


class BuildZipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.out = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.out.cleanup()

    def build(self, *args: str, token: str | None = TOKEN) -> subprocess.CompletedProcess[str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith("STACKTRACE_")}
        if token is not None:
            env["STACKTRACE_REMOTE_TOKEN"] = token
        # A session of its own has no terminal, so the token prompt is skipped.
        return subprocess.run(
            ["sh", str(ROOT / "scripts/build_cowork_zip.sh"), str(Path(self.out.name, "p.zip")), *args],
            capture_output=True, text=True, check=False, env=env, start_new_session=True,
        )

    def names(self) -> list[str]:
        import zipfile

        with zipfile.ZipFile(Path(self.out.name, "p.zip")) as archive:
            return sorted(archive.namelist())

    def read(self, name: str) -> str:
        import zipfile

        with zipfile.ZipFile(Path(self.out.name, "p.zip")) as archive:
            return archive.read(name).decode()

    def test_the_zip_holds_the_claude_plugin_and_the_token(self) -> None:
        result = self.build()

        self.assertEqual(result.returncode, 0, result.stderr)
        names = self.names()
        for name in (".claude-plugin/plugin.json", "hooks/hooks.json", "monitors/monitors.json", "scripts/session_start.sh", "scripts/policy_hook.sh", "skills/status/SKILL.md"):
            self.assertIn(name, names)
        for prefix in ("devin/", "tests/", "docs/", ".codex-plugin/", ".cursor-plugin/", "hooks/codex.json", "hooks/cursor.json"):
            self.assertFalse([n for n in names if n.startswith(prefix)], prefix)
        self.assertEqual(self.read("cowork/enroll.env"), f"STACKTRACE_REMOTE_TOKEN={TOKEN}\n")

    def test_a_wheel_goes_in_beside_the_token(self) -> None:
        wheel = Path(self.out.name, "stacktrace_cli-0.27.0-py3-none-any.whl")
        wheel.write_text("wheel")

        self.build("--wheel", str(wheel))

        self.assertIn("cowork/stacktrace_cli-0.27.0-py3-none-any.whl", self.names())
        self.assertIn("STACKTRACE_CLI_WHEEL=stacktrace_cli-0.27.0-py3-none-any.whl\n", self.read("cowork/enroll.env"))

    def test_no_token_or_an_unplain_token_builds_nothing(self) -> None:
        for token in (None, "two words", "a'quote"):
            with self.subTest(token=token):
                result = self.build(token=token)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(Path(self.out.name, "p.zip").exists())
                self.assertNotIn(TOKEN, result.stderr + result.stdout)


class PipedBuildTests(unittest.TestCase):
    """`curl ... | sh` has no checkout: the script downloads the plugin."""

    SHA = "0123456789abcdef0123456789abcdef01234567"

    def setUp(self) -> None:
        self.work = tempfile.TemporaryDirectory()
        work = Path(self.work.name)
        self.log = work / "curl.log"
        self.zip = work / "p.zip"
        self.bin = work / "bin"
        self.bin.mkdir()

    def tearDown(self) -> None:
        self.work.cleanup()

    def serve(self, ref: str) -> None:
        """A `curl` that serves the pinned SHA and the plugin as of `ref`."""
        tarball = Path(self.work.name, "plugin.tar.gz")
        archive = subprocess.run(
            ["git", "-C", str(ROOT), "archive", "--format=tar.gz", "--prefix=stacktrace-plugin-x/", ref],
            capture_output=True, check=True,
        )
        tarball.write_bytes(archive.stdout)
        curl = self.bin / "curl"
        curl.write_text(
            "#!/bin/sh\n"
            'for url; do :; done\n'
            'echo "$url" >>"%s"\n'
            'case $url in\n'
            '  *marketplace.json) echo \'{"source": {"sha": "%s"}}\' ;;\n'
            '  *codeload*) cat "%s" ;;\n'
            "  *) exit 22 ;;\n"
            "esac\n" % (self.log, self.SHA, tarball)
        )
        curl.chmod(0o755)

    def build(self, **extra: str) -> subprocess.CompletedProcess[str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith("STACKTRACE_")}
        env.update(PATH=f"{self.bin}{os.pathsep}{env['PATH']}", STACKTRACE_REMOTE_TOKEN=TOKEN, **extra)
        script = (ROOT / "scripts/build_cowork_zip.sh").read_text()
        return subprocess.run(
            ["sh", "-s", "--", str(self.zip)], input=script, cwd=self.work.name,
            capture_output=True, text=True, check=False, env=env, start_new_session=True,
        )

    def test_it_downloads_the_commit_production_pins(self) -> None:
        self.serve("HEAD")

        result = self.build()

        self.assertEqual(result.returncode, 0, result.stderr)
        urls = self.log.read_text().splitlines()
        self.assertTrue(urls[0].endswith("/main/.claude-plugin/marketplace.json"))
        self.assertEqual(urls[1], f"https://codeload.github.com/stacktrace-ai/stacktrace-plugin/tar.gz/{self.SHA}")
        import zipfile

        with zipfile.ZipFile(self.zip) as archive:
            self.assertIn("scripts/session_start.sh", archive.namelist())
            self.assertEqual(archive.read("cowork/enroll.env").decode(), f"STACKTRACE_REMOTE_TOKEN={TOKEN}\n")
        self.assertIn("Organization settings > Plugins & skills", result.stdout)

    def test_a_named_ref_is_downloaded_in_place_of_the_pin(self) -> None:
        self.serve("HEAD")

        self.build(STACKTRACE_PLUGIN_REF="v9.9.9")

        self.assertEqual(
            self.log.read_text().splitlines(),
            ["https://codeload.github.com/stacktrace-ai/stacktrace-plugin/tar.gz/v9.9.9"],
        )

    def test_a_release_without_cowork_support_is_refused(self) -> None:
        self.serve("v0.4.3")

        result = self.build()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not support Claude Cowork yet", result.stderr)
        self.assertFalse(self.zip.exists())


if __name__ == "__main__":
    unittest.main()
