#!/usr/bin/env python3
"""Detach one metadata-only Stacktrace lifecycle event from Claude Code."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from typing import Any

FORWARDED_FIELDS = ("session_id", "transcript_path", "cwd", "hook_event_name")
ALLOWED_EVENTS = {"Stop", "SessionEnd"}


def filtered_event(raw: str) -> dict[str, str] | None:
    try:
        document = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(document, dict):
        return None
    event = document.get("hook_event_name")
    if event not in ALLOWED_EVENTS:
        return None
    if not all(
        isinstance(document.get(field), str) and document[field]
        for field in FORWARDED_FIELDS
    ):
        return None
    return {field: document[field] for field in FORWARDED_FIELDS}


def launch(
    event: dict[str, str],
    *,
    find_executable: Callable[[str], str | None] = shutil.which,
    popen: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
) -> bool:
    executable = find_executable("stacktrace")
    if executable is None:
        return False
    options: dict[str, Any] = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        options["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        options["start_new_session"] = True
    process = popen([executable, "remote", "auto-sync", "run"], **options)
    if process.stdin is None:
        return False
    process.stdin.write(json.dumps(event, separators=(",", ":")).encode("utf-8"))
    process.stdin.close()
    return True


def main() -> int:
    event = filtered_event(sys.stdin.read())
    if event is not None:
        try:
            launch(event)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
