"""Codex uses the same CLI failure wrapper and a separate native hook manifest."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CodexHooksTests(unittest.TestCase):
    def test_failed_cli_never_emits_a_native_deny(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'stacktrace'
            for exit_code in (1, 2, 127):
                with self.subTest(exit_code=exit_code):
                    binary.write_text("#!/bin/sh\nprintf '%s\\n' '{\"hookSpecificOutput\":{\"permissionDecision\":\"deny\"}}'\nexit " + str(exit_code) + "\n")
                    binary.chmod(0o700)
                    result = subprocess.run(['sh', str(ROOT / 'scripts/policy_hook.sh'), 'admit', '--agent-kind', 'codex'], input='{}', capture_output=True, text=True, env={**os.environ, 'HOME': str(root), 'PATH': str(root) + os.pathsep + os.environ['PATH']})
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, '')

    def test_codex_manifest_selects_only_its_native_hooks(self):
        manifest = json.loads((ROOT / '.codex-plugin/plugin.json').read_text())
        hooks = json.loads((ROOT / manifest['hooks']).read_text())['hooks']
        self.assertEqual(set(hooks), {'SessionStart', 'PreToolUse'})
        for event, operation in (('SessionStart', 'register'), ('PreToolUse', 'admit')):
            handler = hooks[event][0]['hooks'][0]
            self.assertIn('policy_hook.sh', handler['command'])
            self.assertIn(operation + ' --agent-kind codex', handler['command'])
            self.assertNotIn('onFailure', handler)


if __name__ == '__main__':
    unittest.main()
