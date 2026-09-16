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

    expected_skills = {"setup", "status", "detect"}
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
    if not isinstance(configured, dict) or set(configured) != {"Stop", "SessionEnd"}:
        fail("hooks must contain exactly Stop and SessionEnd")
    expected_command = '"${CLAUDE_PLUGIN_ROOT}"/scripts/launch_auto_sync.py'
    for event, matchers in configured.items():
        if not isinstance(matchers, list) or len(matchers) != 1:
            fail(f"{event} must contain one matcher group")
        matcher = matchers[0]
        if not isinstance(matcher, dict):
            fail(f"{event} matcher group must be an object")
        handlers = matcher.get("hooks")
        if not isinstance(handlers, list) or len(handlers) != 1:
            fail(f"{event} must contain one handler")
        handler = handlers[0]
        if handler != {"type": "command", "command": expected_command, "async": True}:
            fail(f"{event} must invoke only the async metadata launcher")

    launcher = ROOT / "scripts" / "launch_auto_sync.py"
    if not launcher.is_file() or not launcher.stat().st_mode & stat.S_IXUSR:
        fail("scripts/launch_auto_sync.py must exist and be executable")

    forbidden = [ROOT / ".mcp.json", ROOT / "settings.json", ROOT / "bin"]
    present = [path.name for path in forbidden if path.exists()]
    if present:
        fail(f"unexpected automatic plugin surfaces: {', '.join(present)}")

    print("plugin scaffold ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
