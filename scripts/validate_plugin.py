#!/usr/bin/env python3
"""Validate the intended Stacktrace Claude Code plugin surface."""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing {relative}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {relative}: {exc}")
    if not isinstance(document, dict):
        fail(f"{relative} must contain a JSON object")
    return document


def main() -> int:
    manifest = load_json(".claude-plugin/plugin.json")
    marketplace = load_json(".claude-plugin/marketplace.json")
    hooks = load_json("hooks/hooks.json")

    if manifest.get("name") != "stacktrace":
        fail("plugin name must be stacktrace")
    if "version" in manifest:
        fail("plugin manifest must omit version so the source commit drives updates")

    plugins = marketplace.get("plugins")
    if marketplace.get("name") != "stacktrace":
        fail("marketplace must be named stacktrace")
    if not isinstance(plugins, list):
        fail("marketplace must contain a plugin list")
    if len(plugins) != 1 or plugins[0] != {"name": "stacktrace", "source": "./"}:
        fail("marketplace must list exactly the repository-local stacktrace plugin")

    expected_skills = {"setup", "status", "detect", "dismiss", "mute", "why"}
    skills_root = ROOT / "skills"
    observed_skills = {
        path.name
        for path in skills_root.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }
    if observed_skills != expected_skills:
        fail(
            f"expected skills {sorted(expected_skills)}, found {sorted(observed_skills)}"
        )

    configured = hooks.get("hooks")
    if not isinstance(configured, dict) or set(configured) != {
        "Stop",
        "SessionEnd",
        "PostToolUseFailure",
    }:
        fail("hooks must contain exactly Stop, SessionEnd and PostToolUseFailure")

    sync_launcher = {
        "type": "command",
        "command": '"${CLAUDE_PLUGIN_ROOT}"/scripts/launch_auto_sync.py',
        "async": True,
    }
    # ADR-0002: detection is synchronous because its output has to be read --
    # Claude Code never reads an async hook's stdout -- and it fires on tool
    # failure rather than at Stop, because a loop inside one long turn produces
    # no Stop until the loop is already over.
    detector = {
        "type": "command",
        "command": '"${CLAUDE_PLUGIN_ROOT}"/scripts/detect_and_notify.py',
        "timeout": 5,
    }
    expected_handlers = {
        "Stop": [sync_launcher],
        "SessionEnd": [sync_launcher],
        "PostToolUseFailure": [detector],
    }

    for event, matchers in configured.items():
        if not isinstance(matchers, list) or len(matchers) != 1:
            fail(f"{event} must contain one matcher group")
        matcher = matchers[0]
        if not isinstance(matcher, dict):
            fail(f"{event} matcher group must be an object")
        if matcher.get("hooks") != expected_handlers[event]:
            fail(f"{event} must invoke exactly its documented handlers, in order")

    for name in ("launch_auto_sync.py", "detect_and_notify.py"):
        script = ROOT / "scripts" / name
        if not script.is_file() or not script.stat().st_mode & stat.S_IXUSR:
            fail(f"scripts/{name} must exist and be executable")

    forbidden = [ROOT / ".mcp.json", ROOT / "settings.json", ROOT / "bin"]
    present = [path.name for path in forbidden if path.exists()]
    if present:
        fail(f"unexpected automatic plugin surfaces: {', '.join(present)}")

    print("plugin scaffold ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
