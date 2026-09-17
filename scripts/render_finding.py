#!/usr/bin/env python3
"""Render one finding the Stacktrace CLI has already decided to surface.

This process makes no detection decision. It asks the CLI what is pending for
this session, formats the answer for Claude Code's terminal, and exits. It owns
no queue, no cursor, and no suppression state -- see ADR-0002.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from typing import Any

#: Severity drives the gutter and headline colour. Three plain SGR codes rather
#: than truecolour, so the finding inherits whatever palette the operator's
#: terminal theme already uses.
SEVERITY_COLOURS = {"low": "2", "medium": "33", "high": "31"}

#: Claude Code pipes hook stdout, so `isatty` is always false here and cannot
#: gate colour. `NO_COLOR` is the honoured signal instead.
COLOUR_MODES = ("auto", "always", "never")

#: A Stop hook that waits on the CLI delays the operator's next prompt. The
#: query is a local read, so anything slower than this is a broken install
#: rather than a slow answer.
QUERY_TIMEOUT_SECONDS = 2.0

REQUIRED_FIELDS = ("rule_id", "severity", "confidence", "title", "recommendation")


def use_colour(environ: dict[str, str]) -> bool:
    mode = environ.get("STACKTRACE_COLOR", "auto")
    if mode not in COLOUR_MODES:
        mode = "auto"
    if mode == "never":
        return False
    if mode == "always":
        return True
    return environ.get("NO_COLOR") is None


def query(
    session_id: str,
    *,
    find_executable: Callable[[str], str | None] = shutil.which,
    run: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> dict[str, Any] | None:
    """Ask the CLI for this session's pending finding, or None."""
    executable = find_executable("stacktrace")
    if executable is None:
        return None
    try:
        completed = run(
            [executable, "notify", "next", "--session", session_id, "--format", "json"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=QUERY_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    try:
        document = json.loads(completed.stdout or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    finding = document.get("finding")
    if not isinstance(finding, dict):
        return None
    if not all(isinstance(finding.get(field), str) and finding[field] for field in REQUIRED_FIELDS):
        return None
    if finding["severity"] not in SEVERITY_COLOURS:
        return None
    return finding


def render(finding: dict[str, Any], *, colour: bool) -> str:
    """Six lines at most. An alert longer than a glance is one people learn to skip."""
    tone = SEVERITY_COLOURS[finding["severity"]]
    gutter = f"\x1b[{tone}m▐\x1b[0m " if colour else "▐ "
    dim = (lambda text: f"\x1b[2m{text}\x1b[0m") if colour else (lambda text: text)

    headline = f"{finding['severity']} · {finding['confidence']} · {finding['rule_id']}"
    if colour:
        headline = f"\x1b[1;{tone}m{headline}\x1b[0m"
    fired = finding.get("fired_here")
    if isinstance(fired, int) and fired > 1:
        headline += dim(f" ×{fired} here")

    lines = [headline, finding["title"]]

    evidence = finding.get("evidence")
    if isinstance(evidence, list):
        lines.extend(f"  • {item}" for item in evidence if isinstance(item, str))

    # Coverage is stated only when it is partial. Full coverage changes nothing
    # about how the claim should be read, and belongs in `/stacktrace:why`.
    coverage = finding.get("coverage")
    if isinstance(coverage, dict) and coverage.get("full") is False:
        reason = coverage.get("reason")
        if isinstance(reason, str) and reason:
            lines.append(dim(f"  ◐ partial coverage · {reason}"))

    lines.append(f"  → {finding['recommendation']}")

    # The CLI decides when the operator still needs the action row; showing it
    # on every finding is the noise this format exists to avoid.
    if finding.get("show_actions") is True:
        lines.append(dim("/stacktrace:dismiss · /stacktrace:mute · /stacktrace:why"))

    return "\n" + "\n".join(gutter + line for line in lines)


def main() -> int:
    try:
        document = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, UnicodeError):
        return 0
    if not isinstance(document, dict) or document.get("hook_event_name") != "Stop":
        return 0
    session_id = document.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return 0

    finding = query(session_id)
    if finding is None:
        return 0

    print(json.dumps({"systemMessage": render(finding, colour=use_colour(dict(os.environ)))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
