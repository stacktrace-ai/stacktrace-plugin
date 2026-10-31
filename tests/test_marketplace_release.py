"""Development merges must not select production plugin code."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MarketplaceReleaseTests(unittest.TestCase):
    def test_production_source_uses_an_exact_commit_from_the_official_repository(self):
        (entry,) = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())["plugins"]
        source = entry["source"]
        self.assertIsInstance(source, dict, "relative sources follow development merges")
        self.assertEqual(source["source"], "url")
        self.assertEqual(source["url"], "https://github.com/stacktrace-ai/stacktrace-plugin.git")
        self.assertRegex(source["sha"], r"^[0-9a-f]{40}$")
        self.assertNotIn("ref", source)

    def test_entry_display_fields_are_present_and_well_formed(self):
        (entry,) = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())["plugins"]
        self.assertTrue(entry["displayName"])
        self.assertTrue(entry["description"])
        self.assertTrue(entry["author"]["name"])
        self.assertTrue(entry["homepage"])
        self.assertTrue(entry["repository"])
        self.assertTrue(entry["keywords"])

    def test_validator_ignores_an_unreleased_plugin_manifest_edit(self):
        """An ordinary commit changing plugin.json must not force the pinned
        marketplace entry out of sync or fail CI (the sha intentionally stays
        fixed until a promotion PR advances it)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            manifest_path = root / ".claude-plugin/plugin.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["description"] = "An unreleased description from ordinary development"
            manifest_path.write_text(json.dumps(manifest))
            result = subprocess.run(
                [sys.executable, str(root / "scripts/validate_plugin.py")],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_validator_rejects_mutable_sources_and_invalid_commit_pins(self):
        url_source = {"source": "url", "url": "https://github.com/stacktrace-ai/stacktrace-plugin.git"}
        sources = [
            "./", url_source, {**url_source, "ref": "main"}, {**url_source, "ref": "v0.3.2"},
            {**url_source, "sha": "1234567"}, {**url_source, "sha": "A" * 40},
            {**url_source, "sha": ""}, {**url_source, "sha": None},
            {**url_source, "sha": "a" * 40, "url": "https://github.com/another/repository.git"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            path = root / ".claude-plugin/marketplace.json"
            marketplace = json.loads(path.read_text())
            for source in sources:
                with self.subTest(source=source):
                    marketplace["plugins"][0]["source"] = source
                    path.write_text(json.dumps(marketplace))
                    result = subprocess.run(
                        [sys.executable, str(root / "scripts/validate_plugin.py")],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("commit", result.stderr)


if __name__ == "__main__":
    unittest.main()
