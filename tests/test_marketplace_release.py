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
        self.assertEqual(source["source"], "github")
        self.assertEqual(source["repo"], "stacktrace-ai/stacktrace-plugin")
        self.assertRegex(source["sha"], r"^[0-9a-f]{40}$")
        self.assertNotIn("ref", source)

    def test_validator_rejects_mutable_sources_and_invalid_commit_pins(self):
        github = {"source": "github", "repo": "stacktrace-ai/stacktrace-plugin"}
        sources = [
            "./", github, {**github, "ref": "main"}, {**github, "ref": "v0.3.2"},
            {**github, "sha": "1234567"}, {**github, "sha": "A" * 40},
            {**github, "sha": ""}, {**github, "sha": None},
            {**github, "sha": "a" * 40, "repo": "another/repository"},
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
