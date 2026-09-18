"""Exercise the command boundary with an offline executable stub."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SlackWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.capture = self.path / "argv.json"
        self.executable = self.path / "stacktrace-slack"
        self.executable.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "Path(os.environ['CAPTURE']).write_text(json.dumps(sys.argv[1:]))\n"
            "print(json.dumps({'status':'accepted'}))\n"
            "raise SystemExit(int(os.environ.get('STUB_EXIT', '0')))\n"
        )
        self.executable.chmod(0o700)
        self.environment = {**os.environ, "PATH": str(self.path), "CAPTURE": str(self.capture)}

    def run_workflow(self, value):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/slack.py")],
            input=json.dumps(value), text=True, capture_output=True,
            env=self.environment, check=False,
        )

    def test_connect_passes_literal_labels_without_shell_expansion(self):
        marker = self.path / "should-not-exist"
        label = "$(touch " + str(marker) + ")"
        response = self.run_workflow({
            "action": "connect", "service_url": "https://notify.example",
            "connection": "work", "project_id": "project1", "project_label": label,
        })
        self.assertEqual(response.returncode, 0, response.stderr)
        argv = json.loads(self.capture.read_text())
        self.assertIn(label, argv)
        self.assertIn("connect", argv)
        self.assertFalse(marker.exists())

    def test_four_workflows_preserve_adapter_exit_status(self):
        for action in ("status", "test", "disconnect"):
            with self.subTest(action=action):
                self.environment["STUB_EXIT"] = "7"
                response = self.run_workflow({"action": action})
                self.assertEqual(response.returncode, 7)
                self.assertEqual(json.loads(self.capture.read_text()), ["--connection", "default", action])

    def test_rejects_tokens_publish_and_untrusted_origin(self):
        for value in (
            {"action": "status", "token": "secret"},
            {"action": "publish"},
            {"action": "status", "service_url": "http://example.com"},
            {"action": "status", "service_url": "https://user:secret@example.com"},
            {"action": "connect", "project_id": "/private/project", "project_label": "Demo"},
        ):
            with self.subTest(value=value):
                response = self.run_workflow(value)
                self.assertEqual(response.returncode, 2)
                self.assertFalse(self.capture.exists())
                self.assertNotIn("secret", response.stderr)

    def test_rejects_path_shaped_labels(self):
        for value in (
            {"action": "connect", "project_id": "project1",
             "project_label": "/home/alice/private-project"},
            {"action": "connect", "project_id": "project1",
             "project_label": "Demo", "device_label": "C:\\Users\\alice\\private-project"},
        ):
            with self.subTest(value=value):
                response = self.run_workflow(value)
                self.assertEqual(response.returncode, 2)
                self.assertFalse(self.capture.exists())

    def test_missing_adapter_explains_optional_dependency(self):
        self.executable.unlink()
        response = self.run_workflow({"action": "status"})
        self.assertEqual(response.returncode, 127)
        self.assertIn("optional", response.stderr)
        self.assertIn("Native Stacktrace remains usable", response.stderr)


if __name__ == "__main__":
    unittest.main()
