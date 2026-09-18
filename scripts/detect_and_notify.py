#!/usr/bin/env python3
"""Detect a stalling session from the transcript Claude Code already hands us.

No CLI, no daemon, no state file. Everything this needs is derivable from the
transcript on each firing, which is what keeps it stateless: a streak is read
from the tail of the file, not remembered between runs.

Two outputs, because a finding has two audiences. `systemMessage` is the person
at the terminal. `additionalContext` is Claude, which can reach a person who is
not -- see ADR-0002.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

#: Attempts at one failing call before it stops being a retry and starts being
#: a loop. Below three, "it failed twice" is ordinary work.
STALL_THRESHOLD = 3

#: Read only the tail. A long session's transcript reaches megabytes, and a
#: streak lives at the end of it by definition.
TAIL_BYTES = 512 * 1024

SEVERITY_COLOURS = {"low": "2", "medium": "33", "high": "31"}

#: Volatile substrings that make two runs of the same *error* look different.
#: Applied to the failure output only -- a call's own arguments (paths,
#: line numbers, ports) are exactly what tells two different calls apart, so
#: they must survive normalisation intact. Numbers are normalised only where
#: they're demonstrably volatile (a duration like `1.2s`); a bare number is
#: as likely to be part of the diagnostic itself -- an assertion's expected
#: or actual value, a count -- and erasing it can hide a genuinely different
#: failure behind an identical-looking signature.
_NOISE = (
    (re.compile(r"0x[0-9a-fA-F]+"), "0xX"),
    (
        re.compile(r"\d+(?:\.\d+)?\s*(?:ms|s|secs?|seconds?|mins?|minutes?|hours?|h)\b", re.IGNORECASE),
        "N",
    ),
    (re.compile(r"/[^\s:]+"), "PATH"),
    (re.compile(r"\s+"), " "),
)


def use_colour(environ: dict[str, str]) -> bool:
    mode = environ.get("STACKTRACE_COLOR", "auto")
    if mode == "never":
        return False
    if mode == "always":
        return True
    return environ.get("NO_COLOR") is None


def _bounded(text: str, limit: int) -> str:
    """Cap an identity fragment at `limit` chars. Slicing alone can collide two
    different fragments that happen to share a prefix at least that long, so a
    truncated fragment carries a hash of its untruncated self as a tie-breaker."""
    if len(text) <= limit:
        return text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"{text[:limit]}…{digest}"


def _normalise(value: object, limit: int) -> str:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    for pattern, replacement in _NOISE:
        text = pattern.sub(replacement, text)
    return _bounded(text.strip().lower(), limit)


def _normalise_call(value: object, limit: int) -> str:
    """Preserve the call's identity exactly -- case, whitespace, and all.
    Unlike `_normalise`, nothing here is folded: a case-sensitive filename or
    meaningful spacing inside quoted data can be the only thing distinguishing
    two different calls, which is the whole reason the call is in the signature."""
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    return _bounded(text, limit)


def signature(tool_name: str, call_input: object, content: object) -> str:
    """Identity of one failing *call with its diagnostic*, not of one error
    string.

    The call has to be in the key: a failed Bash result opens with `Exit code 1`,
    so an error-only signature makes every failing command in a session look like
    the same failure -- three unrelated ones would report as a stall. The
    diagnostic body has to be in the key too: the same call can fail for
    different reasons behind the same status line, and only the body tells
    those apart. Both sides are noise-stripped first so incidental volatility
    -- a temp path, a timestamp, a line number -- doesn't split one real streak.
    """
    text = content if isinstance(content, str) else json.dumps(content, sort_keys=True)
    return f"{tool_name}|{_normalise_call(call_input, 200)}|{_normalise(text, 500)}"


def is_truncated(transcript: Path) -> bool:
    """Whether the tail read could have cut off attempts older than the window."""
    try:
        return transcript.stat().st_size > TAIL_BYTES
    except OSError:
        return False


def read_attempts(transcript: Path) -> list[tuple[str, bool, str]]:
    """Every tool result in the transcript tail, oldest first, as (signature, failed, tool)."""
    try:
        with transcript.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            stream.seek(max(0, stream.tell() - TAIL_BYTES))
            raw = stream.read().decode("utf-8", "replace")
    except OSError:
        return []

    calls: dict[str, tuple[str, object]] = {}
    results: list[tuple[str, bool, str]] = []
    for line in raw.splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue  # A partial first line is expected when seeking into the file.
        if not isinstance(record, dict):
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue  # A truthy non-dict `message` (e.g. a list) must not crash the hook.
        blocks = message.get("content")
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and isinstance(block.get("id"), str):
                calls[block["id"]] = (str(block.get("name", "?")), block.get("input"))
            elif block.get("type") == "tool_result":
                tool, call_input = calls.get(str(block.get("tool_use_id")), ("?", None))
                # is_error arrives as a bool or as the string "True".
                failed = str(block.get("is_error", "")).lower() == "true"
                results.append((signature(tool, call_input, block.get("content")), failed, tool))
    return results


def streak(attempts: list[tuple[str, bool, str]]) -> tuple[int, str] | None:
    """Length of the trailing run of one identical failure, and the tool's name."""
    if not attempts or not attempts[-1][1]:
        return None
    target, _, tool = attempts[-1]
    count = 0
    for sig, failed, _tool in reversed(attempts):
        if sig != target or not failed:
            break
        count += 1
    return count, tool


def finding_for(count: int, tool: str) -> dict[str, Any]:
    return {
        "rule_id": "stacktrace-progress-stall",
        "severity": "medium",
        "confidence": "high",
        "title": f"{tool} has failed {count} times with the same error and no change in between",
        "evidence": [
            f"{count} consecutive {tool} failures · identical error signature",
            "0 successful runs between them",
        ],
        "recommendation": "This isn't converging. Change the approach or hand it back.",
        "coverage": {
            "full": True,
            "reason": None,
            "note": "Read from the transcript tail; older attempts may be outside the window.",
        },
    }


def render(finding: dict[str, Any], *, colour: bool) -> str:
    """Five lines. An alert longer than a glance is one people learn to skip."""
    tone = SEVERITY_COLOURS[finding["severity"]]
    gutter = f"\x1b[{tone}m▐\x1b[0m " if colour else "▐ "
    dim = (lambda text: f"\x1b[2m{text}\x1b[0m") if colour else (lambda text: text)

    headline = f"{finding['severity']} · {finding['confidence']} · {finding['rule_id']}"
    if colour:
        headline = f"\x1b[1;{tone}m{headline}\x1b[0m"

    lines = [headline, finding["title"]]
    lines.extend(f"  • {item}" for item in finding["evidence"])
    coverage = finding["coverage"]
    if not coverage["full"]:
        lines.append(dim(f"  ◐ partial coverage · {coverage['reason']}"))
    lines.append(f"  → {finding['recommendation']}")
    return "\n" + "\n".join(gutter + line for line in lines)


def notice_for(finding: dict[str, Any]) -> str:
    """What Claude is told. Deliberately bounded: report, do not investigate."""
    return (
        f"Stacktrace finding ({finding['rule_id']}, {finding['severity']}): "
        f"{finding['title']} "
        "If the user may be away from the terminal, call PushNotification with a one-line "
        "summary of this finding; that tool suppresses itself when they are present, so "
        "calling it costs nothing when they are here. Do not investigate the finding, do not "
        "change what you were doing, and do not repeat it in your reply -- it is already on "
        "their screen."
    )


def main() -> int:
    try:
        document = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, UnicodeError):
        return 0
    if not isinstance(document, dict):
        return 0
    event = document.get("hook_event_name")
    if event not in {"PostToolUseFailure", "PostToolUse"}:
        return 0
    transcript = document.get("transcript_path")
    if not isinstance(transcript, str) or not transcript:
        return 0

    path = Path(transcript)
    attempts = read_attempts(path)
    found = streak(attempts)
    # Fire on the threshold only. The fourth identical failure is the same
    # finding, and re-announcing it is how an alert becomes wallpaper -- this is
    # also what keeps suppression stateless.
    if found is None or found[0] != STALL_THRESHOLD:
        return 0
    # A truncated tail whose streak runs all the way to the edge of the window
    # -- or is immediately preceded by an orphan result whose own tool_use fell
    # outside it -- may have more identical failures before it that the read
    # never saw. Either way the boundary isn't clean, so the true count could
    # be anything at or past the threshold; treating this as the one, exact
    # crossing of it would risk re-firing on every later failure instead of
    # the one time the design promises.
    boundary = len(attempts) - found[0]
    preceding = attempts[boundary - 1] if boundary > 0 else None
    if is_truncated(path) and (preceding is None or preceding[2] == "?"):
        return 0

    finding = finding_for(*found)
    print(
        json.dumps(
            {
                "systemMessage": render(finding, colour=use_colour(dict(os.environ))),
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "additionalContext": notice_for(finding),
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
