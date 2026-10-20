#!/usr/bin/env python3
"""Validate the intentionally small Stacktrace host integration surface."""

from __future__ import annotations

import json
import re
import stat
import sys
from pathlib import Path
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(relative: str) -> Any:
    path = ROOT / relative
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing {relative}")
    except json.JSONDecodeError as error:
        fail(f"invalid JSON in {relative}: {error}")


def main() -> int:
    manifest = load_json(".claude-plugin/plugin.json")
    marketplace = load_json(".claude-plugin/marketplace.json")
    hooks = load_json("hooks/hooks.json")
    monitors = load_json("monitors/monitors.json")
    codex = load_json(".codex-plugin/plugin.json")
    if codex != {"name": "stacktrace", "description": "Hook-visible MCP policy admission through the installed Stacktrace CLI.", "hooks": "./hooks/codex.json"}:
        fail("Codex must select its own hooks and keep release metadata in the shared manifest")
    codex_hooks = load_json("hooks/codex.json")
    expected_codex = {}
    for event, command in (("SessionStart", "register"), ("PreToolUse", "admit")):
        group = {"hooks": [{"type": "command", "command": f'sh "${{PLUGIN_ROOT}}/scripts/policy_hook.sh" {command} --agent-kind codex', "timeout": 5}]}
        if event == "PreToolUse":
            group["matcher"] = "^mcp__.*"
        expected_codex[event] = [group]
    if codex_hooks != {"hooks": expected_codex}:
        fail("Codex hooks must delegate registration and MCP admission through the failure wrapper")

    if not isinstance(manifest, dict) or manifest.get("name") != "stacktrace":
        fail("plugin manifest must name stacktrace")
    version = manifest.get("version")
    semver_number = r"(?:0|[1-9][0-9]*)"
    if not isinstance(version, str) or not re.fullmatch(
        rf"{semver_number}\.{semver_number}\.{semver_number}", version
    ):
        fail("plugin manifest must carry a semver version; bump it on every release "
             "or installed copies never see the change")
    if manifest.get("experimental") != {"monitors": "./monitors/monitors.json"}:
        fail("plugin manifest must reference only the monitor declaration")

    plugins = marketplace.get("plugins") if isinstance(marketplace, dict) else None
    entry = (
        plugins[0]
        if isinstance(plugins, list) and len(plugins) == 1 and isinstance(plugins[0], dict)
        else {}
    )
    source = entry.get("source")
    sha = source.get("sha") if isinstance(source, dict) else None
    # The entry's display fields are validated for shape only, not pinned to a
    # commit's plugin.json: the marketplace sha stays fixed across ordinary
    # development commits, so comparing against the working tree would force
    # publishing unreleased metadata or fail CI on an unrelated edit.
    author = entry.get("author")
    display_fields_valid = (
        isinstance(entry.get("displayName"), str) and entry.get("displayName")
        and isinstance(entry.get("description"), str) and entry.get("description")
        and isinstance(author, dict) and isinstance(author.get("name"), str) and author.get("name")
        and isinstance(entry.get("homepage"), str) and entry.get("homepage")
        and isinstance(entry.get("repository"), str) and entry.get("repository")
        and isinstance(entry.get("keywords"), list) and entry.get("keywords")
        and all(isinstance(keyword, str) and keyword for keyword in entry.get("keywords"))
    )
    expected_keys = {
        "name", "source", "displayName", "description", "author",
        "homepage", "repository", "keywords",
    }
    if (
        not isinstance(marketplace, dict)
        or marketplace.get("name") != "stacktrace"
        or entry.get("name") != "stacktrace"
        or set(entry) != expected_keys
        or not isinstance(source, dict)
        or source.get("source") != "url"
        or source.get("url") != "https://github.com/stacktrace-ai/stacktrace-plugin.git"
        or "ref" in source
        or not isinstance(sha, str)
        or re.fullmatch(r"[0-9a-f]{40}", sha) is None
        or not display_fields_valid
    ):
        fail("marketplace must pin the official stacktrace plugin to an exact commit "
             "and carry well-formed display fields")

    if monitors != [
        {
            "name": "stacktrace-alerts",
            "command": 'sh "${CLAUDE_PLUGIN_ROOT}/scripts/subscribe.sh"',
            "description": "High-severity Stacktrace findings for this Claude session",
        }
    ]:
        fail("plugin must declare exactly one direct Stacktrace session monitor")

    configured = hooks.get("hooks") if isinstance(hooks, dict) else None
    if not isinstance(configured, dict) or set(configured) != {"SessionStart", "PreToolUse", "UserPromptExpansion"}:
        fail("hooks must contain SessionStart guidance and both synchronous admission events")
    expected_start = {"hooks": [{
        "type": "command",
        "command": 'sh "${CLAUDE_PLUGIN_ROOT}/scripts/session_start.sh" 2>/dev/null || true',
        "timeout": 15,
        "onFailure": "continue",
    }]}
    if configured["SessionStart"] != [expected_start]:
        fail("SessionStart must teach notifications and delegate registration to the CLI")

    for event in ("PreToolUse", "UserPromptExpansion"):
        expected_group = {
            "hooks": [{
                "type": "command",
                "command": 'sh "${CLAUDE_PLUGIN_ROOT}/scripts/policy_hook.sh" admit 2>/dev/null || true',
                "timeout": 5,
                "onFailure": "continue",
            }],
        }
        if event == "PreToolUse":
            expected_group["matcher"] = "^(mcp__.*|Skill|Agent|Task)$"
        if configured[event] != [expected_group]:
            fail(f"{event} must use bounded synchronous admission that continues on failure")

    if not (ROOT / "scripts" / "policy_hook.sh").is_file():
        fail("scripts/policy_hook.sh must normalize failed CLI exits")

    expected_skills = {"findings", "status"}
    skills_root = ROOT / "skills"
    observed_skills = {
        path.name
        for path in skills_root.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }
    if observed_skills != expected_skills:
        fail(f"expected skills {sorted(expected_skills)}, found {sorted(observed_skills)}")

    guidance = ROOT / "scripts" / "session_start.sh"
    if not guidance.is_file() or not guidance.stat().st_mode & stat.S_IXUSR:
        fail("scripts/session_start.sh must exist and be executable")

    forbidden = [ROOT / ".mcp.json", ROOT / "settings.json", ROOT / "bin"]
    present = [path.name for path in forbidden if path.exists()]
    if present:
        fail(f"unexpected plugin-owned runtime surfaces: {', '.join(present)}")

    print("plugin scaffold ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
