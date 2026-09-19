#!/usr/bin/env python3
"""Probe the whole delivery path once and name the single next action.

Written because the obvious check is wrong. `stacktrace daemon status`
answering "not running" is the normal state on a healthy machine: the daemon
is started by a subscriber and exits about five seconds after the last one
leaves, so asking outside a subscribed session always finds it down. A setup
flow that treats that as a failure can never succeed, and one that treats it
as success reports monitoring that is not happening.

What distinguishes the two is whether anything *could* subscribe, which is a
question about the CLI and the host, not about the daemon's current pid. So
this walks the path in dependency order and stops at the first thing that
actually blocks delivery:

    CLI on PATH -> CLI has `daemon` -> session id -> daemon (informational)

Slack is probed separately and never changes the native verdict: it is an
optional second destination, and letting it colour the primary path is how a
working install gets reported as broken.

Prints a human report by default, `--format json` for a caller that wants the
fields. Exits 0 when findings can reach this session, 1 when they cannot, and
2 only when the probe itself could not run.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import Any

GIT_INSTALL = (
    "uv tool install --force --from "
    "git+https://github.com/stacktrace-ai/stacktrace.git stacktrace-cli"
)

# Long enough for a cold python start behind `uv tool`, short enough that a
# wedged CLI cannot hang a skill the user is waiting on.
PROBE_TIMEOUT = 15.0


def _run(argv: list[str]) -> tuple[int, str]:
    try:
        done = subprocess.run(
            argv, capture_output=True, text=True, timeout=PROBE_TIMEOUT, check=False
        )
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, ""
    except OSError as error:  # pragma: no cover - defensive
        return 126, str(error)
    return done.returncode, (done.stdout or done.returncode and done.stderr or done.stdout).strip()


def probe() -> dict[str, Any]:
    report: dict[str, Any] = {}

    path = shutil.which("stacktrace")
    report["cli_path"] = path
    if path is None:
        report["verdict"] = "cli-missing"
        return report

    code, version = _run([path, "--version"])
    report["cli_version"] = version if code == 0 else None

    daemon_code, _ = _run([path, "daemon", "--help"])
    report["daemon_command"] = daemon_code == 0
    if daemon_code != 0:
        report["verdict"] = "cli-stale"
        return report

    session = os.environ.get("CLAUDE_CODE_SESSION_ID") or None
    report["session_id"] = session

    status_code, status_text = _run([path, "daemon", "status"])
    report["daemon_running"] = status_code == 0
    report["daemon_status_text"] = status_text

    if session is None:
        report["verdict"] = "no-session-id"
        return report

    # A running daemon proves a subscriber exists, which proves the monitor
    # started. A stopped one proves nothing either way, so it is not a failure.
    report["verdict"] = "subscribed" if status_code == 0 else "ready-unsubscribed"
    return report


def probe_slack() -> dict[str, Any]:
    """Optional, and never allowed to change the native verdict."""
    adapter = shutil.which("stacktrace-slack")
    if adapter is None:
        return {"state": "absent"}
    url = os.environ.get("STACKTRACE_SLACK_URL")
    if not url:
        return {"state": "unconfigured"}
    code, output = _run([adapter, "--service-url", url, "--connection", "default", "status"])
    if code != 0:
        return {"state": "error"}
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return {"state": "unreadable"}
    return {
        "state": "connected" if parsed.get("subscribed") else "pending",
        "delivered": (parsed.get("delivery") or {}).get("counts", {}).get("delivered"),
    }


VERDICTS = {
    "cli-missing": (
        "Findings cannot reach this session.",
        "The stacktrace CLI is not on this process's PATH.",
        "Run /stacktrace:configure to install it. If it was installed after Claude "
        "started, Claude must be fully restarted — a reload cannot refresh an "
        "inherited PATH.",
    ),
    "cli-stale": (
        "Findings cannot reach this session.",
        "The installed CLI has no `daemon` command, so nothing can subscribe.",
        f"Install a build that has it:\n    {GIT_INSTALL}\nThen restart Claude.",
    ),
    "no-session-id": (
        "Findings cannot be routed to this session.",
        "CLAUDE_CODE_SESSION_ID is unset, so there is no session identity to "
        "deliver to.",
        "Expected outside an interactive Claude session. Nothing to fix if this "
        "was run from a plain shell.",
    ),
    "ready-unsubscribed": (
        "Ready. No monitor is currently subscribed.",
        "The CLI can subscribe and the session has an identity. The daemon is "
        "down, which is normal: it runs only while a subscriber holds it open.",
        "If the plugin is installed, restart Claude — the monitor starts at "
        "session start and cannot be started mid-session. If this session began "
        "after the plugin was installed, check that background monitors are "
        "available in this host.",
    ),
    "subscribed": (
        "Monitoring is live.",
        "A subscriber is holding the daemon open for this session.",
        "Nothing to do.",
    ),
}


def render(report: dict[str, Any], slack: dict[str, Any]) -> str:
    verdict = report["verdict"]
    headline, because, action = VERDICTS[verdict]
    ok = verdict in {"subscribed", "ready-unsubscribed"}

    def mark(good: bool) -> str:
        return "ok  " if good else "FAIL"

    lines = [f"Stacktrace: {headline}", ""]
    lines.append(f"  [{mark(report['cli_path'] is not None)}] CLI        {report.get('cli_version') or report.get('cli_path') or 'not on PATH'}")
    if report["cli_path"] is not None:
        lines.append(f"  [{mark(report.get('daemon_command', False))}] daemon cmd {'present' if report.get('daemon_command') else 'missing from this build'}")
    if "session_id" in report:
        lines.append(f"  [{mark(bool(report.get('session_id')))}] session    {report.get('session_id') or 'CLAUDE_CODE_SESSION_ID unset'}")
    if "daemon_running" in report:
        state = "running (a monitor is subscribed)" if report["daemon_running"] else "not running (no subscriber — normal when idle)"
        lines.append(f"  [ -- ] daemon     {state}")

    slack_state = slack["state"]
    slack_text = {
        "absent": "adapter not installed (optional)",
        "unconfigured": "installed, no STACKTRACE_SLACK_URL set (optional)",
        "error": "unreachable or not paired",
        "unreadable": "responded with something unparseable",
        "pending": "paired but not subscribed",
        "connected": f"connected, {slack.get('delivered')} delivered",
    }[slack_state]
    lines.append(f"  [ -- ] Slack      {slack_text}")

    # Keep a multi-line action inside the report's left margin; an install
    # command that starts at column zero reads as output, not as instruction.
    action_block = action.replace("\n", "\n        ")
    lines += ["", f"  Why:  {because}", f"  Next: {action_block}", ""]
    if not ok:
        lines.append("  Slack state never changes this verdict; the native path is independent.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()

    try:
        report = probe()
        slack = probe_slack()
    except Exception as error:  # noqa: BLE001 - a doctor must not add a failure
        print(f"doctor could not complete its probe: {error}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps({"native": report, "slack": slack}, indent=2, sort_keys=True))
    else:
        print(render(report, slack))

    return 0 if report["verdict"] in {"subscribed", "ready-unsubscribed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
