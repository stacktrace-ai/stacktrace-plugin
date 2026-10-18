"""Claude native hooks translated into runner contract version 1.

No policy evaluation, daemon transport, or lifecycle implementation belongs here.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

API_VERSION = 1
MESSAGE = "Stacktrace blocked this action."


def _name(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096 or "\x00" in value:
        raise ValueError("invalid_component")
    return value


def subject_from_hook(payload: dict[str, object]) -> dict[str, object] | None:
    event = payload.get("hook_event_name")
    kind, name, source = "", "", ""
    if event == "PreToolUse":
        tool = payload.get("tool_name")
        provenance = payload.get("mcp_server")
        if provenance is not None or isinstance(tool, str) and tool.startswith("mcp__"):
            if not isinstance(provenance, dict):
                raise ValueError("mcp_provenance_required")
            kind, name, source = (
                "mcp_tool",
                _name(provenance.get("name")),
                _name(provenance.get("source")),
            )
        elif tool in ("Skill", "Agent", "Task"):
            tool_input = payload.get("tool_input")
            if not isinstance(tool_input, dict):
                raise ValueError("invalid_component")
            if tool == "Skill":
                kind, name = "skill", _name(tool_input.get("skill"))
            else:
                if tool_input.get("subagent_type") is None:
                    return None
                name = _name(tool_input.get("subagent_type"))
                if ":" not in name:
                    return None
                kind = "plugin_agent"
        else:
            return None
    elif event == "UserPromptExpansion":
        if payload.get("expansion_type") != "slash_command":
            return None
        kind, name = "command", _name(payload.get("command_name"))
    else:
        return None
    return {"action_kind": kind, "name": name, "source": source}


def scope_from_environment(environment: Mapping[str, str]) -> dict[str, object]:
    project = _name(environment.get("CLAUDE_PROJECT_DIR"))
    if not Path(project).is_absolute():
        raise ValueError("launch_project_required")
    explicit = environment.get("CLAUDE_CONFIG_DIR")
    config_root = Path(explicit).expanduser() if explicit else Path.home() / ".claude"
    if not config_root.is_absolute():
        raise ValueError("absolute_config_required")
    global_config = config_root / ".claude.json" if explicit else Path.home() / ".claude.json"
    return {
        "agent_kind": "claude-code",
        "config_root": str(config_root.resolve()),
        "global_config": str(global_config.resolve()),
        "project_root": str(Path(project).resolve()),
    }


def request(payload: dict[str, object], environment: Mapping[str, str]) -> dict[str, object] | None:
    if payload.get("hook_event_name") == "SessionStart":
        return {
            "operation": "session_start",
            "scope": scope_from_environment(environment),
            "remote": environment.get("CLAUDE_CODE_REMOTE") == "true",
        }
    subject = subject_from_hook(payload)
    if subject is None:
        return None
    return {
        "operation": "authorize",
        "scope": scope_from_environment(environment),
        "subject": subject,
    }


def deny(payload: dict[str, object], decision: dict[str, object]) -> dict[str, object]:
    message = MESSAGE
    if decision.get("description"):
        message += f"\nPolicy rule: {decision['description']}"
    message += "\nView policy: stacktrace remote policy show"
    if payload.get("hook_event_name") == "UserPromptExpansion":
        return {
            "decision": "block",
            "reason": message,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptExpansion",
                "suppressOriginalPrompt": True,
            },
        }
    if payload.get("hook_event_name") == "PreToolUse":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": message,
            }
        }
    raise ValueError("uncovered_event")
