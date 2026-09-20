#!/usr/bin/env python3
"""Read and write this plugin's presentation preferences.

One file, `~/.claude/stacktrace-plugin.json`, holding how this host shows an
alert. Nothing about delivery, policy or a credential goes in it (ADR-0005).

A script rather than a paragraph telling the model to write JSON. A model
writing this file by hand has three ways to go wrong that a reader cannot see
afterwards: it can replace the file instead of updating it, losing keys it was
not asked about; it can write something that does not parse, which the hook then
silently treats as absent; and it can write a value the hook does not recognise,
which reads as a preference that was recorded and is not.

Usage:
    preferences.py get
    preferences.py set desktop_notifications true
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

#: Every key this plugin understands, and what it defaults to when absent.
#:
#: The hook treats an unreadable or missing file as "nothing turned off", so a
#: default here has to be the same answer the hook reaches on its own.
DEFAULTS: dict[str, bool] = {
    "desktop_notifications": True,
}


def path() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / (
        "stacktrace-plugin.json"
    )


def read(file: Path | None = None) -> dict[str, object]:
    """Whatever is on disk, or nothing.

    Absent, unreadable and malformed are the same answer on purpose, and the
    same answer the hook reaches: a preferences file is not load-bearing, and
    failing a session over one would be worse than ignoring it.
    """
    target = path() if file is None else file
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return document if isinstance(document, dict) else {}


def write(key: str, value: bool, file: Path | None = None) -> dict[str, object]:
    """Set one key, keeping everything else that was there.

    Read-modify-write through a temporary file in the same directory, so a
    crash or a full disk leaves the previous file rather than half of a new
    one. Unknown keys already present are preserved: this plugin is not the
    only thing that may ever write here, and dropping a key because we do not
    recognise it is how a shared file becomes unsafe to share.
    """
    if key not in DEFAULTS:
        raise KeyError(f"unknown preference: {key}")
    target = path() if file is None else file
    document = read(target)
    document[key] = value
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=".stacktrace-", suffix=".json")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return document


def effective(file: Path | None = None) -> dict[str, bool]:
    """What is in force: the file where it is understood, defaults elsewhere."""
    document = read(path() if file is None else file)
    return {
        key: value if isinstance(value := document.get(key, default), bool) else default
        for key, default in DEFAULTS.items()
    }


def main(argv: list[str]) -> int:
    if len(argv) == 1 and argv[0] == "get":
        for key, value in sorted(effective().items()):
            print(f"{key}: {'on' if value else 'off'}")
        return 0
    if len(argv) == 3 and argv[0] == "set" and argv[2] in ("true", "false"):
        try:
            write(argv[1], argv[2] == "true")
        except KeyError:
            print(f"Unknown preference. Known: {', '.join(sorted(DEFAULTS))}.", file=sys.stderr)
            return 2
        except OSError:
            print(f"Could not write {path()}.", file=sys.stderr)
            return 1
        print(f"{argv[1]}: {'on' if argv[2] == 'true' else 'off'}")
        return 0
    print("Usage: preferences.py get | preferences.py set <key> <true|false>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
