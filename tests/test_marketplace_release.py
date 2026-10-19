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

    def test_entry_mirrors_plugin_manifest_display_fields(self):
        manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
        (entry,) = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())["plugins"]
        for field in ("displayName", "description", "author", "homepage", "repository", "keywords"):
            self.assertEqual(entry[field], manifest[field], f"entry {field} must mirror plugin.json")

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
