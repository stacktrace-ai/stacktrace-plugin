#!/usr/bin/env python3
"""Dispatch an explicit Slack workflow to the installed, optional local adapter.

Connection management and queue recovery only. Publishing findings is the
daemon's job and stays out of this bridge deliberately: the monitor feed is a
notification stream, not a publish API, and reconstructing a finding from its
text would invent a second schema.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
# Separator-free path forms that a bare "no slash or backslash" rule can't
# catch: a Windows drive-relative reference (C:private) or a bare Unix home
# shorthand (~ or ~alice). Anything with an actual "/" or "\" is rejected
# directly in the label check below, which covers absolute, relative, UNC,
# and home paths with a separator without needing to enumerate their forms.
PATH_SHAPED = re.compile(r"\A(?:[A-Za-z]:|~)")


def arguments(request: dict) -> list[str]:
    """Build argv from a small typed request. No shell expansion or token inputs."""
    allowed = {"action", "service_url", "connection", "project_id", "project_label", "device_label"}
    if not isinstance(request, dict) or set(request) - allowed:
        raise ValueError("Use only the documented Slack workflow fields.")
    action = request.get("action")
    if action not in {"connect", "status", "test", "flush", "disconnect"}:
        raise ValueError("Choose connect, status, test, flush, or disconnect.")
    connection = request.get("connection", "default")
    if not isinstance(connection, str) or not IDENTIFIER.fullmatch(connection):
        raise ValueError("Use a simple connection name.")
    result = ["--connection", connection]
    service_url = request.get("service_url")
    if service_url is not None:
        if not isinstance(service_url, str) or any(ord(c) < 32 for c in service_url):
            raise ValueError("Use an HTTPS Slack service origin.")
        try:
            service_url.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Use an HTTPS Slack service origin.") from None
        url = urlsplit(service_url)
        if (url.scheme != "https" or not url.hostname or url.username is not None
                or url.password is not None or url.query or url.fragment or url.path not in ("", "/")):
            raise ValueError("Use an HTTPS Slack service origin.")
        result += ["--service-url", service_url]
    result += [action]
    if action == "connect":
        project_id = request.get("project_id")
        if not isinstance(project_id, str) or not IDENTIFIER.fullmatch(project_id):
            raise ValueError("Connect requires a stable opaque project_id, not a path.")
        result += ["--project-id", project_id]
        for name in ("project_label", "device_label"):
            label = request.get(name, "My device" if name == "device_label" else None)
            if not isinstance(label, str):
                raise ValueError("Connect requires short, printable project and device labels.")
            label = label.strip()
            if (not label or len(label) > 80 or not label.isprintable()
                    or "/" in label or "\\" in label or PATH_SHAPED.match(label)):
                raise ValueError(
                    "Connect requires short, printable project and device labels, not filesystem paths."
                )
            result += ["--" + name.replace("_", "-"), label]
    elif any(name in request for name in ("project_id", "project_label", "device_label")):
        raise ValueError("Project and device fields apply only to connect.")
    return result


def timeout_message(action: str) -> str:
    if action == "connect":
        return "Slack workflow timed out. Retry connect to resume pending pairing."
    if action == "flush":
        # Flush is idempotent on event ID, so retrying cannot duplicate a finding.
        return "Slack workflow timed out. Queued findings remain queued; retry flush."
    return f"Slack workflow timed out. Retry {action} if it did not complete."


def main() -> int:
    try:
        raw = sys.stdin.read(8193)
        if len(raw) > 8192:
            raise ValueError("Slack workflow request is too large.")
        request = json.loads(raw)
        argv = arguments(request)
    except (ValueError, TypeError):
        print("Invalid Slack workflow request; see /stacktrace:slack usage.", file=sys.stderr)
        return 2
    action = request["action"]
    executable = shutil.which("stacktrace-slack")
    if not executable:
        print(
            "The optional stacktrace-slack adapter is not installed. Install the reviewed "
            "Slack app package described in README.md, then retry. Native Stacktrace remains usable.",
            file=sys.stderr,
        )
        return 127
    try:
        return subprocess.run([executable, *argv], shell=False, check=False, timeout=180).returncode
    except subprocess.TimeoutExpired:
        print(timeout_message(action), file=sys.stderr)
        return 124
    except OSError:
        print("Could not start the optional Slack adapter. Check its installation.", file=sys.stderr)
        return 126


if __name__ == "__main__":
    raise SystemExit(main())
