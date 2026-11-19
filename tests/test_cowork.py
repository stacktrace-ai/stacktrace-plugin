"""The Cowork zip (ADR-0014): its hooks make each boot ready, then run the
plugin's own scripts. The plugin's own hooks and scripts never call it."""

from __future__ import annotations

import copy
import io
import json
import os
import shutil
import socket
import subprocess
import tarfile
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path

from test_plugin import Stubs, isolated

ROOT = Path(__file__).resolve().parents[1]
#: A token in the shape of a real one, made up for these tests.
TOKEN = "stk_test_4f0c7a8e1b2c4d3e8f90"
PIN = "stacktrace-cli==0.27.0"
INSTALL = "uv tool install --quiet --compile-bytecode"
DECIDING = ("PreToolUse", "UserPromptExpansion", "UserPromptSubmit")
#: The Cowork zip's own files. Each hook in it calls one of the two wrappers.
COWORK_FILES = ("hooks.json", "setup.sh", "session_start.sh", "policy_hook.sh")

CLI = """#!/bin/sh
echo "cli $* token=${STACKTRACE_REMOTE_TOKEN:-none} api=${STACKTRACE_REMOTE_API_URL:-none}" >>"$STUB_LOG"
case "$1" in
  --version) echo "stacktrace 0.27.0 (openaca 0.15.0)" ;;
  telemetry) echo off ;;
  remote)
    case "$*" in
      *"hooks status"*) printf '{"desired_revision": %s}\\n' "${STUB_REVISION:-87}" ;;
      *"hooks admit"*) echo "stdin $(cat)" >>"$STUB_LOG" ;;
      *) cat >/dev/null ;;
    esac ;;
esac
exit 0
"""


def cowork_hooks_from(main: dict[str, object]) -> dict[str, object]:
    """What `cowork/hooks.json` must be for the plugin's own `hooks.json`."""

    def handler(command: str, timeout: int) -> dict[str, object]:
        return {"type": "command", "command": command, "timeout": timeout, "onFailure": "continue"}

    def policy(wait: int, timeout: int) -> dict[str, object]:
        return handler(f'sh "${{CLAUDE_PLUGIN_ROOT}}/cowork/policy_hook.sh" {wait} admit 2>/dev/null || true', timeout)

    hooks: dict[str, list[dict[str, object]]] = {}
    for event, groups in main["hooks"].items():  # type: ignore[union-attr]
        hooks[event] = []
        for group in groups:
            group = copy.deepcopy(group)
            if event == "SessionStart":
                group["hooks"] = [handler('sh "${CLAUDE_PLUGIN_ROOT}/cowork/session_start.sh" --agent-kind claude-code 2>/dev/null || true', 60)]
            elif event in DECIDING:
                # A hook that decides waits for the boot, at most 50 seconds.
                group["hooks"] = [policy(50, 60)]
            else:
                group["hooks"] = [policy(0, group["hooks"][0]["timeout"])]
            hooks[event].append(group)
    # A Cowork VM keeps no transcript, so the CLI journals the turn from these
    # (stacktrace ADR-0260).
    hooks["PostToolUse"].append({"hooks": [policy(0, 5)], "matcher": "^(Write|Edit|MultiEdit|NotebookEdit)$"})
    hooks["Stop"] = [{"hooks": [policy(0, 5)]}]
    return hooks


class SeparationTests(unittest.TestCase):
    """The plugin's own hooks and scripts are the same for every host."""

    def test_the_plugins_own_hooks_and_scripts_never_reach_the_cowork_folder(self) -> None:
        own = [ROOT / "hooks/hooks.json", *sorted((ROOT / "scripts").glob("*.sh")), *sorted((ROOT / "devin").rglob("*"))]
        for path in own:
            if path.is_file() and path.name != "build_cowork_zip.sh":
                with self.subTest(path=path.relative_to(ROOT)):
                    text = path.read_text(encoding="utf-8")
                    self.assertNotIn("cowork", text.lower())

    def test_the_cowork_hooks_are_the_plugins_own_after_the_boot_setup(self) -> None:
        # A hook added to the plugin fails here until the Cowork zip has it too.
        main = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
        cowork = json.loads((ROOT / "cowork/hooks.json").read_text(encoding="utf-8"))

        self.assertEqual(cowork["hooks"], cowork_hooks_from(main))

    def test_every_cowork_hook_answers_within_its_timeout(self) -> None:
        cowork = json.loads((ROOT / "cowork/hooks.json").read_text(encoding="utf-8"))
        for event, groups in cowork["hooks"].items():
            for group in groups:
                for hook in group["hooks"]:
                    with self.subTest(event=event):
                        self.assertEqual(hook["onFailure"], "continue")
                        if " 50 admit" in hook["command"]:
                            self.assertGreaterEqual(hook["timeout"], 60)
        session = cowork["hooks"]["SessionStart"][0]["hooks"][0]
        wait = int((ROOT / "cowork/session_start.sh").read_text().split('setup.sh" ')[1].split()[0])
        # The wait, then the plugin's own session start with its own limit.
        self.assertLessEqual(wait + 15, session["timeout"])


def clock_ms() -> int:
    """`clock` in `cowork/setup.sh`: the kernel's uptime, else CLOCK_MONOTONIC."""
    try:
        whole, part = Path("/proc/uptime").read_text().split()[0].split(".")
        return int(whole) * 1000 + int(part) * 10
    except OSError:
        return int(time.clock_gettime(time.CLOCK_MONOTONIC) * 1000)


class FakeDaemon:
    """A daemon socket that answers `policy_status` with `STUB_REVISION`."""

    def __init__(self, path: Path) -> None:
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(str(path))
        self.listener.listen(64)
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self) -> None:
        while True:
            try:
                connection, _ = self.listener.accept()
            except OSError:
                return
            with connection:
                connection.settimeout(1)
                try:
                    request = connection.makefile("rb").readline()
                    if request and json.loads(request).get("type") == "policy_status":
                        revision = json.loads(os.environ.get("STUB_REVISION", "87"))
                        reply = {"version": 1, "type": "policy_status", "status": {"desired_revision": revision}}
                        connection.sendall(json.dumps(reply).encode() + b"\n")
                except OSError:
                    pass

    def close(self) -> None:
        # On Linux, `close` alone leaves a thread in `accept` serving.
        try:
            self.listener.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.listener.close()


class CoworkVmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stubs = Stubs()
        self.home = tempfile.TemporaryDirectory()
        self.plugin = tempfile.TemporaryDirectory()
        self.extra = tempfile.TemporaryDirectory(dir="/tmp")
        shutil.copytree(ROOT / "scripts", Path(self.plugin.name, "scripts"))
        Path(self.plugin.name, "cowork").mkdir()
        for name in COWORK_FILES:
            shutil.copy(ROOT / "cowork" / name, Path(self.plugin.name, "cowork", name))
        self.log = Path(self.extra.name, "calls.log")
        self.log.write_text("")
        tools = Path(self.extra.name, "bin")
        tools.mkdir()
        for name in ("cat", "chmod", "grep", "find", "python3"):
            (tools / name).symlink_to(shutil.which(name))  # type: ignore[arg-type]
        self.tools = tools
        self.uv(install="ok")
        self.curl(exit_code=0)
        self.boot = "boot-a"
        # A daemon that answers on its socket.
        self.socket = Path(self.extra.name, "d.sock")
        self.daemon = FakeDaemon(self.socket)

    def tearDown(self) -> None:
        self.daemon.close()
        for directory in (self.stubs, self.home, self.plugin, self.extra):
            directory.cleanup()

    def uv(self, install: str, delay: int = 0) -> None:
        """A `uv` that records its arguments and, on `ok`, installs the CLI stub."""
        body = (
            'mkdir -p "$HOME/.local/bin"\n'
            f"cat >\"$HOME/.local/bin/stacktrace\" <<'STUB'\n{CLI}STUB\n"
            'chmod 755 "$HOME/.local/bin/stacktrace"\n'
            if install == "ok"
            else "exit 1\n"
        )
        path = self.tools / "uv"
        path.write_text(f'#!/bin/sh\necho "uv $*" >>"$STUB_LOG"\nsleep {delay}\n{body}')
        path.chmod(0o755)

    def curl(self, exit_code: int) -> None:
        path = self.tools / "curl"
        path.write_text(f'#!/bin/sh\necho "curl $*" >>"$STUB_LOG"\nexit {exit_code}\n')
        path.chmod(0o755)

    def enroll(self, text: str) -> None:
        (Path(self.plugin.name, "cowork") / "enroll.env").write_text(text)

    def environment(self, entrypoint: str = "remote_cowork") -> dict[str, str]:
        env = isolated(self.home.name, self.stubs, cli=False, daemon=True)
        env["PATH"] = os.pathsep.join([str(self.tools), env["PATH"]])
        env.update(
            CLAUDE_CODE_ENTRYPOINT=entrypoint,
            CLAUDE_CODE_REMOTE="true",
            STUB_LOG=str(self.log),
            STACKTRACE_BOOT_ID=self.boot,
            STACKTRACE_DAEMON_SOCKET=str(self.socket),
        )
        return env

    def run_start(self, entrypoint: str = "remote_cowork") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["sh", str(Path(self.plugin.name, "cowork/session_start.sh")), "--agent-kind", "claude-code"],
            input=json.dumps({"hook_event_name": "SessionStart", "source": "startup"}),
            capture_output=True, text=True, check=False, env=self.environment(entrypoint),
        )

    def hook(self, wait: int = 50, entrypoint: str = "remote_cowork") -> subprocess.Popen[str]:
        """A hook started now. It reads its input after this boot's setup."""
        return subprocess.Popen(
            ["sh", str(Path(self.plugin.name, "cowork/policy_hook.sh")), str(wait), "admit"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=self.environment(entrypoint),
        )

    def run_hook(self, wait: int = 50, payload: str = '{"hook_event_name":"UserPromptSubmit"}', entrypoint: str = "remote_cowork") -> int:
        process = self.hook(wait, entrypoint)
        process.communicate(payload, timeout=60)
        return process.returncode

    def calls(self) -> list[str]:
        return self.log.read_text().splitlines()

    def installs(self) -> list[str]:
        return [c for c in self.calls() if c.startswith("uv ")]

    def registers(self) -> list[str]:
        return [c for c in self.calls() if c.startswith("cli remote policy hooks register")]

    def configures(self) -> list[str]:
        return [c for c in self.calls() if c.startswith("cli remote configure")]

    def starts(self) -> list[str]:
        return [c for c in self.calls() if c.startswith("cli daemon start")]

    def settle(self, registers: int = 1) -> None:
        """Wait for the record of the project, which setup starts and does not wait for."""
        deadline = time.monotonic() + 10
        while len(self.registers()) < registers and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(len(self.registers()), registers)

    def state(self, name: str) -> Path:
        return Path(self.home.name, ".local/state/stacktrace", name)

    def ready(self) -> str:
        marker = self.state("cowork-ready")
        return marker.read_text().strip() if marker.exists() else ""

    def no_policy(self) -> None:
        """The daemon answers, and holds no policy for two seconds of asking."""
        os.environ["STUB_REVISION"] = "null"
        os.environ["STACKTRACE_COWORK_POLICY_SECONDS"] = "2"
        self.addCleanup(os.environ.pop, "STUB_REVISION", None)
        self.addCleanup(os.environ.pop, "STACKTRACE_COWORK_POLICY_SECONDS", None)

    def message(self, result: subprocess.CompletedProcess[str]) -> str:
        return str(json.loads(result.stdout).get("systemMessage", ""))

    # Session start.

    def test_session_start_installs_the_pinned_cli_and_registers_with_the_token(self) -> None:
        self.enroll(f"STACKTRACE_REMOTE_TOKEN={TOKEN}\n")

        result = self.run_start()

        self.assertEqual(result.returncode, 0)
        self.assertIn(f"{INSTALL} {PIN}", self.calls())
        self.assertEqual([f"cli remote configure token={TOKEN} api=none"], self.configures())
        # Then the plugin's own session start runs, with the hook's input.
        self.assertIn("hookSpecificOutput", json.loads(result.stdout))
        self.assertNotIn("not connected", self.message(result))
        self.assertEqual(self.ready(), "boot-a")

    def test_the_wheel_the_zip_carries_is_installed_instead_of_the_pin(self) -> None:
        self.enroll(f"STACKTRACE_REMOTE_TOKEN={TOKEN}\nSTACKTRACE_CLI_WHEEL=stacktrace_cli-0.27.0-py3-none-any.whl\n")
        wheel = Path(self.plugin.name, "cowork/stacktrace_cli-0.27.0-py3-none-any.whl")
        wheel.write_text("")

        self.run_start()

        self.assertIn(f"{INSTALL} {wheel}", self.calls())

    def test_a_wheel_name_with_a_path_is_ignored(self) -> None:
        self.enroll("STACKTRACE_CLI_WHEEL=../../etc/passwd\n")

        self.run_start()

        self.assertIn(f"{INSTALL} {PIN}", self.calls())

    def test_only_the_known_names_with_plain_values_are_taken(self) -> None:
        self.enroll(
            "STACKTRACE_REMOTE_API_URL=https://api.example.net\n"
            "STACKTRACE_REMOTE_TOKEN=two words\n"
            "PATH=/tmp/evil\n"
        )

        self.daemon.close()

        self.run_hook(wait=2)

        # No token to save, and the daemon starts with the API's address.
        self.assertEqual(self.configures(), [])
        self.assertIn("cli daemon start --no-reasoning token=none api=https://api.example.net", self.starts())

    def test_a_failed_install_says_so_once_and_the_task_continues(self) -> None:
        self.uv(install="fail")

        result = self.run_start()

        self.assertEqual(result.returncode, 0)
        message = self.message(result)
        self.assertEqual(message.count("Stacktrace is not connected"), 1)
        self.assertIn("Organization settings > Capabilities > Code execution", message)
        self.assertNotIn("daemon", message)
        self.assertIn("boot-a failed 3", self.state("cowork-setup.log").read_text())

    def test_an_api_that_does_not_answer_says_so(self) -> None:
        self.curl(exit_code=56)

        result = self.run_start()

        self.assertIn("api.stacktrace.ai", self.message(result))
        self.assertIn("boot-a failed 4", self.state("cowork-setup.log").read_text())

    def test_a_restart_after_a_ready_boot_asks_nothing_of_the_api(self) -> None:
        # The daemon keeps the policy on disk, so a restart needs no API call.
        self.run_hook()
        self.settle()
        self.assertEqual(len([c for c in self.calls() if c.startswith("curl ")]), 1)
        self.log.write_text("")
        self.boot = "boot-b"

        self.run_hook()

        self.assertEqual([c for c in self.calls() if c.startswith("curl ")], [])
        self.assertEqual(self.ready(), "boot-b")

    def test_the_log_times_each_step_in_milliseconds(self) -> None:
        self.enroll(f"STACKTRACE_REMOTE_TOKEN={TOKEN}\n")

        self.run_hook()

        steps = [line.split()[2:] for line in self.state("cowork-setup.log").read_text().splitlines()]
        self.assertEqual([step for step, _ in steps], ["install", "configure", "policy", "ready"])
        for _, number in steps:
            self.assertRegex(number, r"^[0-9]+$")

    # The hooks that decide.

    def test_the_first_prompt_waits_for_setup_and_then_reaches_admit_with_its_payload(self) -> None:
        # Cowork runs the first prompt's hooks before SessionStart ends.
        self.enroll(f"STACKTRACE_REMOTE_TOKEN={TOKEN}\n")
        payload = '{"hook_event_name":"UserPromptSubmit","transcript_path":""}'

        self.assertEqual(self.run_hook(payload=payload), 0)

        calls = self.calls()
        install = calls.index(f"{INSTALL} {PIN}")
        configure = calls.index(f"cli remote configure token={TOKEN} api=none")
        admit = next(i for i, c in enumerate(calls) if c.startswith("cli remote policy hooks admit"))
        self.assertLess(install, configure)
        self.assertLess(configure, admit)
        # The daemon answers, so setup does not start another.
        self.assertEqual(self.starts(), [])
        self.assertIn(f"stdin {payload}", calls)
        self.assertEqual(self.ready(), "boot-a")

    def test_hooks_that_start_together_set_the_boot_up_once(self) -> None:
        # SessionStart and the first prompt's hooks run at the same time.
        self.uv(install="ok", delay=2)

        hooks = [self.hook() for _ in range(4)]
        for hook in hooks:
            hook.communicate('{"hook_event_name":"UserPromptSubmit"}', timeout=60)
        codes = [hook.returncode for hook in hooks]

        self.assertEqual(codes, [0, 0, 0, 0])
        self.assertEqual(len(self.installs()), 1)
        self.settle(registers=1)
        self.assertEqual(len([c for c in self.calls() if c.startswith("stdin ")]), 4)

    def test_a_ready_boot_is_not_set_up_again(self) -> None:
        self.run_hook()
        self.settle()
        self.log.write_text("")

        self.run_hook()

        self.assertEqual(self.installs() + self.registers(), [])

    def test_a_restarted_vm_is_set_up_again(self) -> None:
        # A restart stops the daemon; the kernel's boot id changes with it.
        self.enroll(f"STACKTRACE_REMOTE_TOKEN={TOKEN}\n")
        self.run_hook()
        self.settle()
        self.log.write_text("")
        self.boot = "boot-b"

        self.run_hook()

        self.settle()
        # The disk stays across a restart: the CLI and the saved token too.
        self.assertEqual(self.installs() + self.configures(), [])
        self.assertEqual(self.ready(), "boot-b")

    def test_a_new_token_is_saved_again(self) -> None:
        self.enroll(f"STACKTRACE_REMOTE_TOKEN={TOKEN}\n")
        self.run_hook()
        self.settle()
        self.boot = "boot-b"
        self.enroll("STACKTRACE_REMOTE_TOKEN=stk_test_9d1e2f3a4b5c6d7e8f01\n")
        # A new zip: its `enroll.env` is newer than the saved token.
        later = time.time() + 5
        os.utime(Path(self.plugin.name, "cowork/enroll.env"), (later, later))

        self.run_hook()

        self.assertEqual(len(self.configures()), 2)

    def test_a_daemon_that_stops_without_a_restart_is_started_again(self) -> None:
        self.run_hook()
        self.settle()
        self.log.write_text("")
        # The socket file stays, but nothing answers on it.
        self.daemon.close()

        self.run_hook(wait=2)

        self.assertEqual(len(self.starts()), 1)
        self.assertIn("daemon-gone", self.state("cowork-setup.log").read_text())

    def test_a_setup_killed_in_this_boot_does_not_hold_the_boot_back(self) -> None:
        gone = subprocess.Popen(["true"])
        gone.wait()
        lock = self.state("cowork-setup-boot-a.lock")
        lock.mkdir(parents=True)
        (lock / "pid").write_text(f"{gone.pid}\n")

        self.assertEqual(self.run_hook(), 0)

        self.assertEqual(self.ready(), "boot-a")
        self.assertFalse(lock.exists())

    def test_a_setup_that_runs_holds_the_boot_for_itself(self) -> None:
        # Another hook's setup holds the lock and runs: this hook starts none.
        lock = self.state("cowork-setup-boot-a.lock")
        lock.mkdir(parents=True)
        (lock / "pid").write_text(f"{os.getpid()} {clock_ms()}\n")

        self.run_hook(wait=1)

        self.assertEqual(self.installs(), [])
        self.assertTrue(lock.exists())

    def test_a_setup_that_hangs_past_the_limit_does_not_hold_the_boot_back(self) -> None:
        # Measured on the clock that does not step, never the wall clock. The
        # limit is three minutes; a new CI machine has been up for less.
        os.environ["STACKTRACE_COWORK_STALE_LOCK_SECONDS"] = "1"
        self.addCleanup(os.environ.pop, "STACKTRACE_COWORK_STALE_LOCK_SECONDS", None)
        lock = self.state("cowork-setup-boot-a.lock")
        lock.mkdir(parents=True)
        (lock / "pid").write_text(f"{os.getpid()} {clock_ms() - 2_000}\n")

        self.assertEqual(self.run_hook(), 0)

        self.assertEqual(self.ready(), "boot-a")
        self.assertIn("stale-lock 1", self.state("cowork-setup.log").read_text())

    def test_a_lock_from_an_earlier_boot_does_not_hold_the_boot_back(self) -> None:
        old = self.state("cowork-setup-boot-old.lock")
        old.mkdir(parents=True)
        (old / "pid").write_text(f"{os.getpid()}\n")

        self.assertEqual(self.run_hook(), 0)

        self.assertEqual(self.ready(), "boot-a")
        self.assertFalse(old.exists())

    def test_a_daemon_without_the_policy_is_not_ready(self) -> None:
        # A daemon that answers but holds no policy lets every action through.
        self.no_policy()

        self.run_hook()

        self.assertEqual(self.ready(), "")
        failed = self.state("cowork-failed").read_text().split()
        self.assertEqual(failed[:2], ["boot-a", "5"])

    def test_a_failed_setup_is_not_waited_on_again(self) -> None:
        self.uv(install="fail")
        self.run_hook()
        self.log.write_text("")

        started = time.monotonic()
        self.run_hook()

        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(self.installs(), [])

    def test_a_hook_that_only_reports_starts_setup_and_does_not_wait(self) -> None:
        self.uv(install="fail", delay=4)

        started = time.monotonic()
        self.run_hook(wait=0, payload='{"hook_event_name":"Stop","transcript_path":""}')

        self.assertLess(time.monotonic() - started, 3)

    def test_outside_cowork_the_zip_installs_nothing_and_reads_no_token(self) -> None:
        self.enroll(f"STACKTRACE_REMOTE_TOKEN={TOKEN}\n")

        self.run_start(entrypoint="cli")
        self.run_hook(entrypoint="cli")

        self.assertEqual([c for c in self.calls() if c.startswith(("uv ", "curl "))], [])
        self.assertFalse(self.state("cowork-setup.log").exists())

    def test_the_log_holds_no_token(self) -> None:
        self.enroll(f"STACKTRACE_REMOTE_TOKEN={TOKEN}\n")
        self.run_hook()
        self.boot = "boot-b"
        self.daemon.close()
        self.run_hook(wait=2)

        self.assertNotIn(TOKEN, self.state("cowork-setup.log").read_text())


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
        with zipfile.ZipFile(Path(self.out.name, "p.zip")) as archive:
            return sorted(archive.namelist())

    def read(self, name: str) -> bytes:
        with zipfile.ZipFile(Path(self.out.name, "p.zip")) as archive:
            return archive.read(name)

    def test_the_zip_holds_the_claude_plugin_and_the_token(self) -> None:
        result = self.build()

        self.assertEqual(result.returncode, 0, result.stderr)
        names = self.names()
        for name in (".claude-plugin/plugin.json", "hooks/hooks.json", "monitors/monitors.json", "scripts/session_start.sh", "scripts/policy_hook.sh", "skills/status/SKILL.md"):
            self.assertIn(name, names)
        for prefix in ("devin/", "tests/", "docs/", ".codex-plugin/", ".cursor-plugin/", "hooks/codex.json", "hooks/cursor.json", "cowork/hooks.json"):
            self.assertFalse([n for n in names if n.startswith(prefix)], prefix)
        self.assertEqual(self.read("cowork/enroll.env").decode(), f"STACKTRACE_REMOTE_TOKEN={TOKEN}\n")

    def test_the_zip_runs_the_cowork_hooks_over_the_plugins_own_scripts(self) -> None:
        self.build()

        self.assertEqual(self.read("hooks/hooks.json"), (ROOT / "cowork/hooks.json").read_bytes())
        for name in ("setup.sh", "session_start.sh", "policy_hook.sh"):
            self.assertEqual(self.read(f"cowork/{name}"), (ROOT / "cowork" / name).read_bytes())
        for script in (ROOT / "scripts").iterdir():
            if script.name not in ("build_cowork_zip.sh", "validate_plugin.py"):
                with self.subTest(script=script.name):
                    self.assertEqual(self.read(f"scripts/{script.name}"), script.read_bytes())

    def test_a_wheel_goes_in_beside_the_token(self) -> None:
        wheel = Path(self.out.name, "stacktrace_cli-0.27.0-py3-none-any.whl")
        wheel.write_text("wheel")

        self.build("--wheel", str(wheel))

        self.assertIn("cowork/stacktrace_cli-0.27.0-py3-none-any.whl", self.names())
        self.assertIn("STACKTRACE_CLI_WHEEL=stacktrace_cli-0.27.0-py3-none-any.whl\n", self.read("cowork/enroll.env").decode())

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

    def serve(self, ref: str, *, without: str | None = None) -> None:
        """A `curl` that serves the pinned SHA and the plugin as of `ref`,
        less the folder `without`. CI's checkout fetches no tags, so a
        fixture is built from `HEAD`, never from a release tag."""
        tarball = Path(self.work.name, "plugin.tar.gz")
        archive = subprocess.run(
            ["git", "-C", str(ROOT), "archive", "--format=tar", "--prefix=stacktrace-plugin-x/", ref],
            capture_output=True, check=True,
        )
        dropped = f"stacktrace-plugin-x/{without}/" if without else None
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as source, tarfile.open(tarball, "w:gz") as served:
            for member in source.getmembers():
                if dropped and (member.name + "/").startswith(dropped):
                    continue
                served.addfile(member, source.extractfile(member) if member.isfile() else None)
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
        with zipfile.ZipFile(self.zip) as archive:
            self.assertIn("scripts/session_start.sh", archive.namelist())
            self.assertIn("cowork/setup.sh", archive.namelist())
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
        # A release from before ADR-0014 has no `cowork` folder.
        self.serve("HEAD", without="cowork")

        result = self.build()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not support Claude Cowork yet", result.stderr)
        self.assertFalse(self.zip.exists())


if __name__ == "__main__":
    unittest.main()
