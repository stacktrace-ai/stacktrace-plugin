"""Pi installs this repository as a Pi package, and OpenCode loads `opencode/stacktrace.ts`.

Both files come from the stacktrace repository (`hooks/pi_extension.ts` and
`hooks/opencode_plugin.ts`) and keep their unreplaced marker, which makes each
run `scripts/policy_hook.sh` beside it.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate(root):
    return subprocess.run([sys.executable, str(root / 'scripts/validate_plugin.py')], capture_output=True, text=True)


def copy():
    directory = tempfile.TemporaryDirectory()
    root = Path(directory.name)
    shutil.copytree(ROOT, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    return directory, root


class PiAndOpenCodeHooksTests(unittest.TestCase):
    def test_the_pi_package_loads_only_the_extension_and_mirrors_the_version(self):
        claude = json.loads((ROOT / '.claude-plugin/plugin.json').read_text())
        package = json.loads((ROOT / 'package.json').read_text())
        self.assertEqual(package['version'], claude['version'])
        self.assertEqual(package['pi'], {'extensions': ['./pi/stacktrace.ts'], 'skills': [], 'prompts': [], 'themes': []})

    def test_each_hook_reaches_the_shared_wrapper_and_asks_for_its_own_kind(self):
        for folder, kind, events in (
            ('pi', 'pi', ('"session_start"', '"input"', '"tool_call"')),
            ('opencode', 'opencode', ('"chat.message"', '"tool.execute.before"')),
        ):
            with self.subTest(folder=folder):
                source = (ROOT / folder / 'stacktrace.ts').read_text()
                self.assertEqual(source.count('"__STACKTRACE_HOOKS__"'), 1)
                self.assertIn('"../scripts/policy_hook.sh"', source)
                self.assertIn('--agent-kind ' + kind, source)
                for event in events:
                    self.assertIn(event, source)

    def test_the_opencode_plugin_exports_one_function(self):
        """OpenCode reads every export of a plugin file as a plugin."""
        source = (ROOT / 'opencode/stacktrace.ts').read_text()
        self.assertEqual(source.count('\nexport '), 1)

    def test_the_opencode_plugin_classifies_mcp_resource_reads_from_their_args(self):
        """`read_mcp_resource` keeps a fixed tool name; its server is in the call's args."""
        source = (ROOT / 'opencode/stacktrace.ts').read_text()
        self.assertIn('"read_mcp_resource"', source)
        self.assertIn('args?.server', source)

    def test_validator_rejects_version_drift_and_more_resources_in_the_pi_package(self):
        for change, message in (
            ({'version': '0.0.1'}, 'The Pi package must load only'),
            ({'pi': {'extensions': ['./pi/stacktrace.ts'], 'skills': ['./skills'], 'prompts': [], 'themes': []}}, 'The Pi package must load only'),
        ):
            with self.subTest(change=change):
                directory, root = copy()
                with directory:
                    path = root / 'package.json'
                    path.write_text(json.dumps({**json.loads(path.read_text()), **change}))
                    result = validate(root)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(message, result.stderr)

    def test_validator_rejects_another_file_or_a_replaced_marker(self):
        for folder in ('pi', 'opencode'):
            with self.subTest(folder=folder, case='extra file'):
                directory, root = copy()
                with directory:
                    (root / folder / 'other.ts').write_text('export default () => {}\n')
                    result = validate(root)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(f'the {folder} folder must hold only', result.stderr)
            with self.subTest(folder=folder, case='marker replaced'):
                directory, root = copy()
                with directory:
                    path = root / folder / 'stacktrace.ts'
                    path.write_text(path.read_text().replace('"__STACKTRACE_HOOKS__"', '"stacktrace remote policy hooks"'))
                    result = validate(root)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn('must keep its marker', result.stderr)


if __name__ == '__main__':
    unittest.main()
