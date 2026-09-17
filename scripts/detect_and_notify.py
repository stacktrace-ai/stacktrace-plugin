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

#: Volatile substrings that make two runs of the same failure look different.
_NOISE = (
    (re.compile(r"0x[0-9a-fA-F]+"), "0xX"),
    (re.compile(r"\d+(?:[.,:]\d+)*"), "N"),
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


def signature(tool_name: str, content: object) -> str:
    """A stable identity for one failure, robust to timestamps, paths and counters."""
    text = content if isinstance(content, str) else json.dumps(content, sort_keys=True)
    first = text.strip().splitlines()[0] if text.strip() else ""
    for pattern, replacement in _NOISE:
        first = pattern.sub(replacement, first)
    return f"{tool_name}:{first.strip().lower()[:160]}"


def read_attempts(transcript: Path) -> list[tuple[str, bool, str]]:
    """Every tool result in the transcript tail, oldest first, as (signature, failed, tool)."""
    try:
        with transcript.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            stream.seek(max(0, stream.tell() - TAIL_BYTES))
            raw = stream.read().decode("utf-8", "replace")
    except OSError:
        return []

    names: dict[str, str] = {}
    results: list[tuple[str, bool, str]] = []
    for line in raw.splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue  # A partial first line is expected when seeking into the file.
        if not isinstance(record, dict):
            continue
        blocks = (record.get("message") or {}).get("content")
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and isinstance(block.get("id"), str):
                names[block["id"]] = str(block.get("name", "?"))
            elif block.get("type") == "tool_result":
                tool = names.get(str(block.get("tool_use_id")), "?")
                # is_error arrives as a bool or as the string "True".
                failed = str(block.get("is_error", "")).lower() == "true"
                results.append((signature(tool, block.get("content")), failed, tool))
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

    found = streak(read_attempts(Path(transcript)))
    # Fire on the threshold only. The fourth identical failure is the same
    # finding, and re-announcing it is how an alert becomes wallpaper -- this is
    # also what keeps suppression stateless.
    if found is None or found[0] != STALL_THRESHOLD:
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
