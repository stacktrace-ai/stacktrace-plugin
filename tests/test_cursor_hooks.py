"""Cursor uses the same CLI failure wrapper and its own native hook manifest."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CursorHooksTests(unittest.TestCase):
    def test_failed_cli_never_emits_a_native_deny(self):
        # Cursor blocks on exit 2 and on a deny it can parse, so neither may escape.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'stacktrace'
            for exit_code in (1, 2, 127):
                with self.subTest(exit_code=exit_code):
                    binary.write_text("#!/bin/sh\nprintf '%s\\n' '{\"permission\":\"deny\"}'\nexit " + str(exit_code) + "\n")
                    binary.chmod(0o700)
                    environment = {**os.environ, 'HOME': str(root), 'PATH': str(root) + os.pathsep + os.environ['PATH']}
                    environment.pop('VIRTUAL_ENV', None)
                    result = subprocess.run(['sh', './scripts/policy_hook.sh', 'admit', '--agent-kind', 'cursor'], cwd=ROOT, input='{}', capture_output=True, text=True, env=environment)
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, '')

    def test_cursor_manifest_selects_only_its_native_hooks(self):
        manifest = json.loads((ROOT / '.cursor-plugin/plugin.json').read_text())
        hooks = json.loads((ROOT / manifest['hooks']).read_text())
        self.assertEqual(hooks['version'], 1)
        self.assertEqual(set(hooks['hooks']), {'sessionStart', 'beforeMCPExecution'})
        for event, operation in (('sessionStart', 'register'), ('beforeMCPExecution', 'admit')):
            handler = hooks['hooks'][event][0]
            self.assertTrue(handler['command'].startswith('sh ./scripts/policy_hook.sh '))
            self.assertIn(operation + ' --agent-kind cursor', handler['command'])
            self.assertNotIn('failClosed', handler)


class CursorVersionTests(unittest.TestCase):
    def test_native_manifests_share_the_same_release_version(self):
        claude = json.loads((ROOT / '.claude-plugin/plugin.json').read_text())
        cursor = json.loads((ROOT / '.cursor-plugin/plugin.json').read_text())
        self.assertEqual(cursor.get('version'), claude['version'])

    def test_validator_rejects_manifest_version_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git', '__pycache__'))
            manifest = root / '.cursor-plugin/plugin.json'
            document = json.loads(manifest.read_text())
            document['version'] = '0.0.1'
            manifest.write_text(json.dumps(document))
            result = subprocess.run([sys.executable, str(root / 'scripts/validate_plugin.py')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('shared release version', result.stderr)


if __name__ == '__main__':
    unittest.main()
