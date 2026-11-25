"""DIAGNOSTIC BRANCH, NEVER MERGE. Replays one unanswered Devin PreToolUse
through the installed CLI's adapter and prints the daemon's own answer."""

import json
import os
import sys
import time

from stacktrace.hooks import devin
from stacktrace.hooks.claude import authorize

payload = json.loads(sys.stdin.read())
try:
    action = devin.action_from_hook(payload, os.environ)
except Exception as error:  # noqa: BLE001
    print("parse_error", type(error).__name__, error)
    sys.exit()
if action is None:
    print("no_action")
    sys.exit()
call = action.get("call")
print(
    "action",
    action.get("action_kind"),
    action.get("name"),
    action.get("source"),
    "keys",
    sorted(action),
    "call_keys",
    sorted(call) if isinstance(call, dict) else None,
    "cwd",
    call.get("cwd") if isinstance(call, dict) else None,
    "project",
    action.get("project_root"),
)
started = time.monotonic()
try:
    result = authorize(action, timeout=20)
    print(
        "result",
        result.outcome,
        result.reason,
        "rule",
        result.rule,
        "detail",
        result.detail,
        "seconds",
        round(time.monotonic() - started, 3),
    )
except Exception as error:  # noqa: BLE001
    print("authorize_error", type(error).__name__, error, round(time.monotonic() - started, 3))
