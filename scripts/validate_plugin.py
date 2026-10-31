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
    if not isinstance(manifest, dict) or manifest.get("name") != "stacktrace":
        fail("plugin manifest must name stacktrace")
    marketplace = load_json(".claude-plugin/marketplace.json")
    hooks = load_json("hooks/hooks.json")
    monitors = load_json("monitors/monitors.json")
    codex = load_json(".codex-plugin/plugin.json")
    if codex != {"name": "stacktrace", "version": manifest.get("version"), "description": "Hook-visible MCP policy admission through the installed Stacktrace CLI.", "hooks": "./hooks/codex.json"}:
        fail("Codex must select its own hooks and mirror the shared release version")
    codex_hooks = load_json("hooks/codex.json")
    expected_codex = {}
    for event, command in (("SessionStart", "register"), ("PreToolUse", "admit")):
        group = {"hooks": [{"type": "command", "command": f'sh "${{PLUGIN_ROOT}}/scripts/policy_hook.sh" {command} --agent-kind codex', "timeout": 5}]}
        if event == "PreToolUse":
            group["matcher"] = "^mcp__.*"
        expected_codex[event] = [group]
    if codex_hooks != {"hooks": expected_codex}:
        fail("Codex hooks must delegate registration and MCP admission through the failure wrapper")
    cursor = load_json(".cursor-plugin/plugin.json")
    # Cursor auto-discovers every skills/*/SKILL.md when the field is absent; an
    # explicit empty list keeps Claude-only skills out of the Cursor surface.
    if cursor != {"name": "stacktrace", "version": manifest.get("version"), "description": "Hook-visible MCP policy admission through the installed Stacktrace CLI.", "hooks": "./hooks/cursor.json", "skills": []}:
        fail("Cursor must select its own hooks, disable skill auto-discovery, and mirror the shared release version")
    # Cursor runs plugin hooks from the plugin root, and fails open without failClosed.
    # sessionStart gets a longer timeout so registration survives daemon recovery (ADR-0009).
    expected_cursor = {
        event: [{"command": f"sh ./scripts/policy_hook.sh {command} --agent-kind cursor", "timeout": timeout}]
        for event, command, timeout in (("sessionStart", "register", 15), ("beforeMCPExecution", "admit", 5))
    }
    if load_json("hooks/cursor.json") != {"version": 1, "hooks": expected_cursor}:
        fail("Cursor hooks must delegate registration and MCP admission through the failure wrapper")

    # Devin installs the `devin` folder (ADR-0012). Its manifest has no hooks
    # field: Devin reads `hooks.json` at the plugin root. The folder carries its
    # own copy of the failure wrapper, so it works when Devin stages it alone.
    if load_json("devin/.devin-plugin/plugin.json") != {"name": "stacktrace", "version": manifest.get("version"), "description": "Hook-visible MCP policy admission through the installed Stacktrace CLI."}:
        fail("Devin must name the plugin and mirror the shared release version")
    expected_devin = {}
    for event, matcher, command, timeout in (("SessionStart", "", "register", 15), ("PreToolUse", "^(mcp__.+|mcp_call_tool)$", "admit", 5)):
        expected_devin[event] = [{"matcher": matcher, "hooks": [{"type": "command", "command": f'sh "${{DEVIN_PLUGIN_ROOT}}/scripts/policy_hook.sh" {command} --agent-kind devin', "timeout": timeout}]}]
    if load_json("devin/hooks.json") != expected_devin:
        fail("Devin hooks must delegate registration and MCP admission through the failure wrapper")
    devin_wrapper = ROOT / "devin" / "scripts" / "policy_hook.sh"
    if not devin_wrapper.is_file() or devin_wrapper.read_bytes() != (ROOT / "scripts" / "policy_hook.sh").read_bytes():
        fail("devin/scripts/policy_hook.sh must be an exact copy of scripts/policy_hook.sh")
    # Devin loads an AGENTS.md, rules/ and skills/ in the plugin root into every
    # session, so nothing else may join the folder.
    devin_files = sorted(str(path.relative_to(ROOT / "devin")) for path in (ROOT / "devin").rglob("*") if path.is_file())
    if devin_files != [".devin-plugin/plugin.json", "hooks.json", "scripts/policy_hook.sh"]:
        fail(f"the Devin folder must hold only its manifest, hooks and wrapper, found {devin_files}")

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
    # Cursor refuses a sha-pinned commit whose tree holds a url-source catalog,
    # which every release carries, so users pin a release tag instead (ADR-0011).
    if load_json(".cursor-plugin/marketplace.json") != {
        "name": "stacktrace",
        "owner": {"name": "Stacktrace AI"},
        "plugins": [{"name": "stacktrace", "source": "./"}],
    }:
        fail("Cursor marketplace must list only this repository's root plugin")

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
