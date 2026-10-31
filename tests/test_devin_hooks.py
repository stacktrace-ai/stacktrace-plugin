"""Devin installs the `devin` folder, which reuses the CLI failure wrapper (ADR-0012)."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'devin'


def validate(root):
    return subprocess.run([sys.executable, str(root / 'scripts/validate_plugin.py')], capture_output=True, text=True)


def copy():
    directory = tempfile.TemporaryDirectory()
    root = Path(directory.name)
    shutil.copytree(ROOT, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    return directory, root


class DevinHooksTests(unittest.TestCase):
    def test_failed_cli_never_reaches_devin_as_a_block(self):
        # Devin blocks on exit 2 and on a `block` decision on stdout, so neither may escape.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'stacktrace'
            for exit_code in (1, 2, 127):
                with self.subTest(exit_code=exit_code):
                    binary.write_text("#!/bin/sh\nprintf '%s\\n' '{\"decision\":\"block\",\"reason\":\"old\"}'\nexit " + str(exit_code) + "\n")
                    binary.chmod(0o700)
                    environment = {**os.environ, 'HOME': str(root), 'PATH': str(root) + os.pathsep + os.environ['PATH']}
                    environment.pop('VIRTUAL_ENV', None)
                    result = subprocess.run(['sh', str(PLUGIN / 'scripts/policy_hook.sh'), 'admit', '--agent-kind', 'devin'], input='{}', capture_output=True, text=True, env=environment)
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, '')

    def test_a_successful_cli_deny_reaches_devin_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'stacktrace'
            binary.write_text("#!/bin/sh\ncat >/dev/null\nprintf '%s\\n' \"$*\" >\"$HOME/args\"\nprintf '%s\\n' '{\"decision\":\"block\",\"reason\":\"r\"}'\n")
            binary.chmod(0o700)
            environment = {**os.environ, 'HOME': str(root), 'PATH': str(root) + os.pathsep + os.environ['PATH'], 'DEVIN_PLUGIN_ROOT': str(PLUGIN)}
            environment.pop('VIRTUAL_ENV', None)
            hooks = json.loads((PLUGIN / 'hooks.json').read_text())
            command = hooks['PreToolUse'][0]['hooks'][0]['command']
            result = subprocess.run(['sh', '-c', command], input='{"hook_event_name":"PreToolUse"}', capture_output=True, text=True, env=environment)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout), {'decision': 'block', 'reason': 'r'})
            self.assertEqual((root / 'args').read_text(), 'remote policy hooks admit --agent-kind devin\n')

    def test_the_hooks_select_registration_and_mcp_calls_only(self):
        hooks = json.loads((PLUGIN / 'hooks.json').read_text())
        self.assertEqual(set(hooks), {'SessionStart', 'PreToolUse'})
        for event, operation in (('SessionStart', 'register'), ('PreToolUse', 'admit')):
            (group,) = hooks[event]
            (handler,) = group['hooks']
            self.assertEqual(handler['type'], 'command')
            self.assertTrue(handler['command'].startswith('sh "${DEVIN_PLUGIN_ROOT}/scripts/policy_hook.sh" '))
            self.assertTrue(handler['command'].endswith(operation + ' --agent-kind devin'))
            self.assertNotIn('fail_closed', handler)
        # Devin matches a matcher as a regex search on tool_name.
        matcher = hooks['PreToolUse'][0]['matcher']
        selected = {'mcp__github__create_issue', 'mcp__fixture__ping', 'mcp_call_tool'}
        others = {'exec', 'read', 'write', 'edit', 'skill', 'run_subagent', 'mcp_list_tools', 'mcp_read_resource', 'xmcp_call_tool'}
        self.assertEqual({name for name in selected | others if re.search(matcher, name)}, selected)

    def test_session_start_gives_registration_room_to_survive_daemon_recovery(self):
        hooks = json.loads((PLUGIN / 'hooks.json').read_text())
        self.assertGreater(hooks['SessionStart'][0]['hooks'][0]['timeout'], hooks['PreToolUse'][0]['hooks'][0]['timeout'])

    def test_the_manifest_mirrors_the_shared_release_version(self):
        claude = json.loads((ROOT / '.claude-plugin/plugin.json').read_text())
        devin = json.loads((PLUGIN / '.devin-plugin/plugin.json').read_text())
        self.assertEqual(devin['name'], 'stacktrace')
        self.assertEqual(devin['version'], claude['version'])
        self.assertNotIn('hooks', devin)

    def test_validator_rejects_a_wrapper_that_drifts_from_the_shared_one(self):
        directory, root = copy()
        with directory:
            with (root / 'devin/scripts/policy_hook.sh').open('a') as wrapper:
                wrapper.write('echo extra\n')
            result = validate(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn('exact copy of scripts/policy_hook.sh', result.stderr)

    def test_validator_rejects_anything_devin_would_load_into_every_session(self):
        for extra in ('AGENTS.md', 'rules/house.md', 'skills/status/SKILL.md'):
            with self.subTest(extra=extra):
                directory, root = copy()
                with directory:
                    path = root / 'devin' / extra
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('extra\n')
                    result = validate(root)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn('the Devin folder must hold only', result.stderr)

    def test_validator_rejects_manifest_version_drift_and_other_hooks(self):
        directory, root = copy()
        with directory:
            manifest = root / 'devin/.devin-plugin/plugin.json'
            document = json.loads(manifest.read_text())
            document['version'] = '0.0.1'
            manifest.write_text(json.dumps(document))
            result = validate(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn('Devin must name the plugin', result.stderr)
        directory, root = copy()
        with directory:
            hooks = root / 'devin/hooks.json'
            document = json.loads(hooks.read_text())
            document['PreToolUse'][0]['matcher'] = ''
            hooks.write_text(json.dumps(document))
            result = validate(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn('Devin hooks must delegate', result.stderr)


if __name__ == '__main__':
    unittest.main()
