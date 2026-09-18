#!/usr/bin/env python3
"""Dispatch an explicit Slack workflow to the installed, optional local adapter."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
PATH_SHAPED = re.compile(r"\A(?:[A-Za-z]:[\\/]|\\\\|~[\\/]|/)")


def arguments(request: dict) -> list[str]:
    """Build argv from a small typed request. No shell expansion or token inputs."""
    allowed = {"action", "service_url", "connection", "project_id", "project_label", "device_label"}
    if not isinstance(request, dict) or set(request) - allowed:
        raise ValueError("Use only the documented Slack workflow fields.")
    action = request.get("action")
    if action not in {"connect", "status", "test", "disconnect"}:
        raise ValueError("Choose connect, status, test, or disconnect.")
    connection = request.get("connection", "default")
    if not isinstance(connection, str) or not IDENTIFIER.fullmatch(connection):
        raise ValueError("Use a simple connection name.")
    result = ["--connection", connection]
    service_url = request.get("service_url")
    if service_url is not None:
        if not isinstance(service_url, str):
            raise ValueError("Use an HTTPS Slack service origin.")
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
            if (not isinstance(label, str) or not label.strip() or len(label) > 80
                    or any(ord(c) < 32 for c in label) or PATH_SHAPED.match(label)):
                raise ValueError(
                    "Connect requires short, printable project and device labels, not filesystem paths."
                )
            result += ["--" + name.replace("_", "-"), label]
    elif any(name in request for name in ("project_id", "project_label", "device_label")):
        raise ValueError("Project and device fields apply only to connect.")
    return result


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
        print("Slack workflow timed out. Retry connect to resume pending pairing.", file=sys.stderr)
        return 124
    except OSError:
        print("Could not start the optional Slack adapter. Check its installation.", file=sys.stderr)
        return 126


if __name__ == "__main__":
    raise SystemExit(main())
