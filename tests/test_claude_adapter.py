"""Native parsing and denial rendering belong to the plugin, without CLI imports."""

import importlib.util
import json
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts/claude_adapter.py"
spec = importlib.util.spec_from_file_location("claude_adapter", PATH)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
ENV = {"CLAUDE_PROJECT_DIR": "/project", "CLAUDE_CONFIG_DIR": "/config"}


class ClaudeAdapterTests(unittest.TestCase):
    def test_native_mcp_provenance_and_launch_root_ignore_prefix_and_cwd(self):
        payload = {
            "hook_event_name": "PreToolUse", "cwd": "/other",
            "tool_name": "mcp__misleading__run",
            "mcp_server": {"name": "github", "source": "project"},
            "tool_input": {"secret": "never forward"},
        }
        self.assertEqual(adapter.request(payload, ENV), {
            "operation": "authorize",
            "scope": {"agent_kind": "claude-code", "config_root": "/config",
                      "global_config": "/config/.claude.json", "project_root": "/project"},
            "subject": {"action_kind": "mcp_tool", "name": "github", "source": "project"},
        })

    def test_all_hook_visible_plugin_paths_strip_content(self):
        for payload, kind, name in [
            ({"hook_event_name": "PreToolUse", "tool_name": "Skill", "tool_input": {"skill": "plugin:deploy", "args": "secret"}}, "skill", "plugin:deploy"),
            ({"hook_event_name": "UserPromptExpansion", "expansion_type": "slash_command", "command_name": "plugin:deploy", "command_args": "secret", "prompt": "secret"}, "command", "plugin:deploy"),
            *[({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"subagent_type": "plugin:review", "prompt": "secret"}}, "plugin_agent", "plugin:review") for tool in ("Agent", "Task")],
        ]:
            with self.subTest(kind=kind, payload=payload):
                request = adapter.request(payload, ENV)
                self.assertEqual(request["subject"], {"action_kind": kind, "name": name, "source": ""})
                self.assertNotIn("secret", json.dumps(request))

    def test_uncovered_tools_and_non_plugin_agents_return_no_request(self):
        for payload in [
            {"hook_event_name": "PreToolUse", "tool_name": "Bash"},
            {"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": {"prompt": "secret"}},
            {"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": {"subagent_type": "Explore"}},
            {"hook_event_name": "UserPromptExpansion", "expansion_type": "other"},
            {"hook_event_name": "Unknown"},
        ]:
            with self.subTest(payload=payload):
                self.assertIsNone(adapter.request(payload, ENV))

    def test_missing_or_invalid_selectors_and_provenance_are_rejected(self):
        for payload in [
            {"hook_event_name": "PreToolUse", "tool_name": "mcp__github__read"},
            {"hook_event_name": "PreToolUse", "mcp_server": {"name": "github"}},
            {"hook_event_name": "PreToolUse", "mcp_server": "bad"},
            {"hook_event_name": "PreToolUse", "tool_name": "Skill", "tool_input": None},
            *[{"hook_event_name": "PreToolUse", "tool_name": "Skill", "tool_input": {"skill": name}} for name in (None, "", "x" * 4097, "bad\x00name")],
        ]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                adapter.request(payload, ENV)

    def test_missing_and_relative_launch_paths_are_rejected(self):
        payload = {"hook_event_name": "SessionStart"}
        for environment in ({}, {**ENV, "CLAUDE_PROJECT_DIR": "relative"}, {**ENV, "CLAUDE_CONFIG_DIR": "relative"}):
            with self.subTest(environment=environment), self.assertRaises(ValueError):
                adapter.request(payload, environment)

    def test_both_hosts_register_only_launch_context(self):
        for remote in (False, True):
            environment = {**ENV, "CLAUDE_CODE_REMOTE": "true" if remote else "false"}
            request = adapter.request({"hook_event_name": "SessionStart", "prompt": "secret", "transcript_path": "/secret", "cwd": "/other"}, environment)
            self.assertEqual(request, {
                "operation": "session_start", "remote": remote,
                "scope": {"agent_kind": "claude-code", "config_root": "/config",
                          "global_config": "/config/.claude.json", "project_root": "/project"},
            })
            self.assertNotIn("secret", json.dumps(request))

    def test_implicit_and_explicit_config_paths_preserve_claude_layout(self):
        implicit = adapter.request({"hook_event_name": "SessionStart"}, {"CLAUDE_PROJECT_DIR": "/project"})
        self.assertEqual(implicit["scope"]["config_root"], str(Path.home() / ".claude"))
        self.assertEqual(implicit["scope"]["global_config"], str(Path.home() / ".claude.json"))
        explicit = adapter.request({"hook_event_name": "SessionStart"}, ENV)
        self.assertEqual(explicit["scope"]["global_config"], "/config/.claude.json")

    def test_denials_explain_only_the_human_rule_and_preserve_native_shapes(self):
        for event in ("UserPromptExpansion", "PreToolUse"):
            payload = {"hook_event_name": event, "prompt": "secret-argument", "tool_input": {"args": "secret-argument"}}
            reply = adapter.deny(payload, {"outcome": "deny", "description": "Block plugin discord@official."})
            output = json.dumps(reply)
            self.assertIn("Stacktrace blocked this action.", output)
            self.assertIn("Policy rule: Block plugin discord@official.", output)
            self.assertIn("stacktrace remote policy show", output)
            for hidden in ("revision", "admission.plugins", "secret-argument"):
                self.assertNotIn(hidden, output)
            native = reply["hookSpecificOutput"]
            self.assertEqual(native["hookEventName"], event)
            if event == "PreToolUse":
                self.assertEqual(native["permissionDecision"], "deny")
            else:
                self.assertEqual(reply["decision"], "block")
                self.assertTrue(native["suppressOriginalPrompt"])

    def test_denials_without_rule_detail_still_block(self):
        reply = adapter.deny({"hook_event_name": "PreToolUse"}, {"outcome": "deny"})
        self.assertEqual(reply["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertNotIn("Policy rule:", json.dumps(reply))

    def test_renderer_rejects_uncovered_events(self):
        with self.assertRaises(ValueError):
            adapter.deny({"hook_event_name": "SessionStart"}, {"outcome": "deny"})


if __name__ == "__main__":
    unittest.main()
