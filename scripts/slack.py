#!/usr/bin/env python3
"""Dispatch an explicit Slack workflow to the installed, optional local adapter.

The adapter's result is parsed and projected, never echoed. Its `status` answer
spreads the whole pairing binding into the body, including the Slack `team_id`
and `user_id`, and a `connect` answer carries the pairing `credential`. Letting
that reach a terminal publishes what the pairing exists to keep private. Letting
it reach an agent transcript is worse, because a transcript is stored and may be
uploaded.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import threading
from urllib.parse import urlsplit

#: Result keys this bridge will print.
#:
#: An allowlist, not a denylist, because the hosted service owns the response
#: shape and can add to it. A denylist would leak the first field someone adds;
#: this withholds it and says how many it withheld.
PRINTABLE_RESULT_KEYS = ("status", "subscribed", "local_queue", "event_id", "outcomes")

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
    if action not in {"connect", "status", "test", "disconnect"}:
        raise ValueError("Choose connect, status, test, or disconnect.")
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
    return f"Slack workflow timed out. Retry {action} if it did not complete."


def projected(line: str) -> str:
    """One line of adapter stdout, with anything identifying removed.

    A line that is not a JSON object is passed through. `connect` prints the
    verification URL and the pairing code that way, and the operator needs
    both: neither is a credential, and the pairing is useless without them.

    A line that is a JSON object is rebuilt from `PRINTABLE_RESULT_KEYS` alone.
    The count of withheld keys is reported rather than the keys themselves,
    because naming them would describe the shape of a document this bridge has
    just decided not to show.
    """
    try:
        document = json.loads(line)
    except ValueError:
        return line
    if not isinstance(document, dict):
        return line
    shown = {key: value for key, value in document.items() if key in PRINTABLE_RESULT_KEYS}
    withheld = len(document) - len(shown)
    rendered = json.dumps(shown, sort_keys=True)
    if withheld:
        return f"{rendered}\n{withheld} identifying field(s) withheld by the plugin."
    return rendered


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
    # Streamed rather than captured. `connect` prints the verification URL and
    # pairing code, then polls while the operator confirms them in Slack, so
    # buffering until exit would show the URL only after the pairing had already
    # finished or timed out.
    #
    # stderr is left inherited. The adapter writes one diagnostic string there
    # and never a result document, so there is nothing to project, and piping it
    # would risk filling that pipe while we are blocked reading stdout.
    try:
        process = subprocess.Popen(
            [executable, *argv],
            shell=False,
            stdout=subprocess.PIPE,
            text=True,
        )
    except OSError:
        print("Could not start the optional Slack adapter. Check its installation.", file=sys.stderr)
        return 126

    expired = False

    def give_up() -> None:
        nonlocal expired
        expired = True
        process.kill()

    watchdog = threading.Timer(180, give_up)
    watchdog.start()
    try:
        if process.stdout is not None:
            for line in process.stdout:
                text = line.rstrip("\n")
                if text.strip():
                    print(projected(text), flush=True)
        process.wait()
    finally:
        watchdog.cancel()
        if process.stdout is not None:
            process.stdout.close()

    if expired:
        print(timeout_message(action), file=sys.stderr)
        return 124
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
