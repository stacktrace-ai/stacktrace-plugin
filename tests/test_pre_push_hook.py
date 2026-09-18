from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK_SCRIPT = ROOT / "scripts" / "git-hooks" / "pre-push"
ZERO_SHA = "0" * 40


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class PrePushHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)

        _run_git(self.repo, "init", "-q", "-b", "main")
        _run_git(self.repo, "config", "user.email", "test@example.com")
        _run_git(self.repo, "config", "user.name", "Test")

        (self.repo / "scripts").mkdir()
        (self.repo / "scripts" / "validate_plugin.py").write_text(
            "raise SystemExit(0)\n", encoding="utf-8"
        )
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "test_noop.py").write_text(
            "import unittest\n\n\n"
            "class NoopTests(unittest.TestCase):\n"
            "    def test_noop(self) -> None:\n"
            "        pass\n",
            encoding="utf-8",
        )
        _run_git(self.repo, "add", "-A")
        _run_git(self.repo, "commit", "-q", "-m", "initial")
        self.head_sha = _run_git(self.repo, "rev-parse", "HEAD")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run_hook(self, stdin: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(HOOK_SCRIPT)],
            cwd=self.repo,
            input=stdin,
            capture_output=True,
            text=True,
        )

    def test_accepts_push_of_checked_out_head(self) -> None:
        stdin = f"refs/heads/main {self.head_sha} refs/heads/main {ZERO_SHA}\n"

        result = self._run_hook(stdin)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_push_of_oid_other_than_checked_out_head(self) -> None:
        (self.repo / "scripts" / "validate_plugin.py").write_text(
            "raise SystemExit(1)\n", encoding="utf-8"
        )
        _run_git(self.repo, "checkout", "-q", "-b", "other")
        _run_git(self.repo, "add", "-A")
        _run_git(self.repo, "commit", "-q", "-m", "would fail validation")
        other_sha = _run_git(self.repo, "rev-parse", "HEAD")
        _run_git(self.repo, "checkout", "-q", "main")
        self.assertEqual(_run_git(self.repo, "rev-parse", "HEAD"), self.head_sha)

        stdin = f"refs/heads/other {other_sha} refs/heads/other {ZERO_SHA}\n"
        result = self._run_hook(stdin)

        self.assertEqual(result.returncode, 1)
        self.assertIn("not the checked-out HEAD", result.stderr)

    def test_ignores_branch_deletions(self) -> None:
        stdin = f"refs/heads/gone {ZERO_SHA} refs/heads/gone {ZERO_SHA}\n"

        result = self._run_hook(stdin)

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
