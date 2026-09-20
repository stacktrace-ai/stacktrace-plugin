from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "preferences.py"


def _module():
    spec = importlib.util.spec_from_file_location("stacktrace_preferences", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PreferenceFileTests(unittest.TestCase):
    def setUp(self):
        self.preferences = _module()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.file = Path(self.directory.name) / "stacktrace-plugin.json"

    def test_absent_unreadable_and_malformed_are_the_same_answer(self):
        # The same answer the hook reaches on its own. A preferences file is not
        # load-bearing, and failing over one would be worse than ignoring it.
        self.assertEqual(self.preferences.effective(self.file), {"desktop_notifications": True})
        for content in ("{", "", "null", "[]", '"a string"'):
            with self.subTest(content=content):
                self.file.write_text(content, encoding="utf-8")
                self.assertEqual(
                    self.preferences.effective(self.file), {"desktop_notifications": True}
                )

    def test_a_non_boolean_falls_back_rather_than_being_believed(self):
        self.file.write_text('{"desktop_notifications": "false"}', encoding="utf-8")

        self.assertTrue(self.preferences.effective(self.file)["desktop_notifications"])

    def test_writing_one_key_keeps_the_others(self):
        # This plugin is not necessarily the only thing that writes here, and
        # dropping a key because we do not recognise it is how a shared file
        # becomes unsafe to share.
        self.file.write_text('{"somebody_elses": 1}', encoding="utf-8")

        self.preferences.write("desktop_notifications", False, self.file)

        document = json.loads(self.file.read_text(encoding="utf-8"))
        self.assertEqual(document, {"somebody_elses": 1, "desktop_notifications": False})

    def test_a_malformed_file_is_replaced_not_merged_into(self):
        self.file.write_text("{ broken", encoding="utf-8")

        self.preferences.write("desktop_notifications", False, self.file)

        self.assertEqual(
            json.loads(self.file.read_text(encoding="utf-8")), {"desktop_notifications": False}
        )

    def test_an_unknown_key_is_refused(self):
        # A key the hook does not read is a preference that was recorded and
        # does nothing, which is worse than being told it is not supported.
        with self.assertRaises(KeyError):
            self.preferences.write("colour_scheme", True, self.file)
        self.assertFalse(self.file.exists())

    def test_the_write_is_atomic(self):
        self.preferences.write("desktop_notifications", True, self.file)
        self.preferences.write("desktop_notifications", False, self.file)

        # No temporary left behind, and nothing half-written beside it.
        self.assertEqual(
            sorted(p.name for p in self.file.parent.iterdir()), ["stacktrace-plugin.json"]
        )

    def test_it_creates_the_directory(self):
        nested = Path(self.directory.name) / "made" / "up" / "stacktrace-plugin.json"

        self.preferences.write("desktop_notifications", False, nested)

        self.assertTrue(nested.is_file())


class HookAgreesWithTheWriterTests(unittest.TestCase):
    """The writer and the reader are a Python script and a POSIX shell script.

    They find the same file by two separate pieces of code, so the only way to
    know they agree is to write with one and read with the other. Unit tests on
    each side pass happily while a preference is recorded somewhere nothing
    looks.
    """

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = Path(self.directory.name)
        self.environment = {
            "CLAUDE_CONFIG_DIR": str(self.config),
            "HOME": self.directory.name,
            "PATH": "/usr/bin:/bin",
        }

    def set_preference(self, key: str, value: str) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "set", key, value],
            capture_output=True,
            text=True,
            env=self.environment,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def guidance(self) -> str:
        result = subprocess.run(
            ["sh", str(ROOT / "scripts" / "session_start.sh")],
            capture_output=True,
            text=True,
            env=self.environment,
            check=True,
        )
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_turning_desktop_off_reaches_the_hook(self) -> None:
        self.set_preference("desktop_notifications", "false")

        self.assertIn("turned desktop notifications off", self.guidance())

    def test_turning_it_back_on_reaches_the_hook(self) -> None:
        self.set_preference("desktop_notifications", "false")
        self.set_preference("desktop_notifications", "true")

        self.assertIn("Desktop notifications are on", self.guidance())

    def test_the_two_agree_on_where_the_file_lives(self) -> None:
        self.set_preference("desktop_notifications", "false")

        self.assertTrue((self.config / "stacktrace-plugin.json").is_file())
        self.assertIn("turned desktop notifications off", self.guidance())


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = {"CLAUDE_CONFIG_DIR": self.directory.name, "PATH": "/usr/bin:/bin"}

    def run_script(self, *arguments):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            capture_output=True,
            text=True,
            env=self.environment,
            check=False,
        )

    def test_get_reports_the_defaults_before_anything_is_written(self):
        result = self.run_script("get")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("desktop_notifications: on", result.stdout)

    def test_set_then_get_round_trips(self):
        self.assertEqual(self.run_script("set", "desktop_notifications", "false").returncode, 0)

        self.assertIn("desktop_notifications: off", self.run_script("get").stdout)

    def test_an_unknown_key_names_the_known_ones(self):
        result = self.run_script("set", "colour_scheme", "true")

        self.assertEqual(result.returncode, 2)
        self.assertIn("desktop_notifications", result.stderr)

    def test_a_non_boolean_value_is_refused(self):
        result = self.run_script("set", "desktop_notifications", "yes")

        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage", result.stderr)


if __name__ == "__main__":
    unittest.main()
