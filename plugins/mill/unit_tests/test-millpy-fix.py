"""Unit tests for millpy-fix.py CLI main().

Loads the module under test via importlib and calls main(argv) in-process.
All external I/O (git, LLM, path resolution) is patched in setUp.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
import uuid
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _safe_rmtree  # noqa: E402

_FIX_PATH = HUB / "plugins" / "mill" / "scripts" / "millpy-fix.py"

_spec = importlib.util.spec_from_file_location("millpy_fix", str(_FIX_PATH))
millpy_fix = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(millpy_fix)


def _make_fixture(tmp_path: Path) -> Path:
    """Create the fake worktree directory tree in tmp_path.

    Returns the review file path.
    """
    plan_dir = tmp_path / "_mill" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)

    overview_text = (
        "# Plan: Test Task\n\n"
        "```yaml\n"
        "task: Test Task\n"
        "slug: test-slug\n"
        "approved: true\n"
        "```\n\n"
        "## Batch Index\n\n"
        "```yaml\n"
        "batches:\n"
        "  - name: test-batch\n"
        "    file: 01-test-batch.md\n"
        "    depends-on: []\n"
        "    verify: null\n"
        "```\n"
    )
    (plan_dir / "00-overview.md").write_text(overview_text, encoding="utf-8")
    (plan_dir / "01-test-batch.md").write_text("# Batch: test-batch\n", encoding="utf-8")

    status_text = (
        "```yaml\n"
        "phase: implementing\n"
        "slug: test-slug\n"
        "task: Test Task\n"
        "branch: test-branch\n"
        "parent: main\n"
        "```\n\n"
        "## Timeline\n\n"
        "```text\n"
        "implementing  2026-01-01T00:00:00Z\n"
        "```\n\n"
        "## Batches\n\n"
        "```yaml\n"
        "batches:\n"
        "  - name: test-batch\n"
        "    state: pending\n"
        "```\n"
    )
    (tmp_path / "_mill" / "status.md").write_text(status_text, encoding="utf-8")

    millhouse_dir = tmp_path / ".millhouse"
    millhouse_dir.mkdir(parents=True, exist_ok=True)
    (millhouse_dir / "config.local.yaml").write_text("{}", encoding="utf-8")

    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / "config.yaml").write_text(
        "roles:\n  implementer:\n    self_fix_rounds: 2\n  fixer:\n    model: haiku\n",
        encoding="utf-8",
    )

    reviews_dir = tmp_path / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    review_file = reviews_dir / "review.md"
    review_file.write_text("# Review\nsome findings here\n", encoding="utf-8")

    return review_file


class TestMillpyFix(unittest.TestCase):

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())
        self.addCleanup(_safe_rmtree.safe_rmtree, self.tmp_path, allowed_root=self.tmp_path, ignore_errors=True)

        self.review_file = _make_fixture(self.tmp_path)

        self.original_cwd = os.getcwd()
        os.chdir(self.tmp_path)
        self.addCleanup(os.chdir, self.original_cwd)

        def _p(target, attr, **kwargs):
            patcher = unittest.mock.patch.object(target, attr, **kwargs)
            mock_obj = patcher.start()
            self.addCleanup(patcher.stop)
            return mock_obj

        self.mock_resolve_git_root = _p(
            millpy_fix._paths, "resolve_git_root",
            return_value=self.tmp_path,
        )
        self.mock_resolve_wiki = _p(
            millpy_fix._paths, "resolve_wiki_path",
            return_value=self.tmp_path / "wiki",
        )
        self.mock_load_config = _p(
            millpy_fix._review_common, "load_config",
            return_value={
                "paths": {"status_md": "_mill/status.md"},
                "roles": {
                    "implementer": {"self_fix_rounds": 2, "model": "sonnethigh"},
                    "fixer": {"model": "haiku"},
                },
                "llm": {"implementer_timeout": 1800},
            },
        )
        self.mock_slug_from_branch = _p(
            millpy_fix._marker, "slug_from_branch",
            return_value="test-slug",
        )
        self.mock_read_branch = _p(
            millpy_fix._status, "read_branch",
            return_value="test-branch",
        )
        self.mock_subprocess_run = _p(
            millpy_fix._subprocess_util, "run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="abc1234\n", stderr=""
            ),
        )
        self.mock_uuid4 = _p(
            millpy_fix.uuid, "uuid4",
            return_value=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        )
        self.mock_reviewers_load = _p(
            millpy_fix._reviewers, "load",
            return_value={
                "haiku": {
                    "type": "single",
                    "provider": "claude",
                    "model": "claude-haiku-4-5-20251001",
                }
            },
        )
        self.mock_reviewers_resolve = _p(
            millpy_fix._reviewers, "resolve",
            return_value={
                "type": "single",
                "provider": "claude",
                "model": "claude-haiku-4-5-20251001",
            },
        )

    def _run_main(self, argv):
        """Run main(argv) with stdout captured. Returns (rc, captured_stdout)."""
        buf = io.StringIO()
        with unittest.mock.patch("sys.stdout", buf):
            rc = millpy_fix.main(argv)
        return rc, buf.getvalue()

    def test_batch_happy_path(self):
        """Batch scope with --batch-name -> success JSON, fixing-test-batch-r1 in timeline."""
        status_path = self.tmp_path / "_mill" / "status.md"

        captured = {}

        def mock_run(prompt_text, *, model, effort, session_id, resume, cwd, timeout):
            captured["prompt_text"] = prompt_text
            captured["resume"] = resume
            return ('{"status":"success","commit_sha":"abc","session_id":"fake"}\n', "fake-session")

        with unittest.mock.patch.object(
            millpy_fix._implementer_claude, "run",
            side_effect=mock_run,
        ):
            rc, out = self._run_main([
                "--scope", "batch",
                "--batch-name", "test-batch",
                "--review-file", str(self.review_file),
                "--round", "1",
            ])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "success")

        # Check that fixing-test-batch-r1 was appended to timeline
        full = millpy_fix._status.read_full(status_path)
        self.assertTrue(
            any(e.startswith("fixing-test-batch-r1") for e in full["timeline"]),
            f"Expected fixing-test-batch-r1 in timeline, got: {full['timeline']}",
        )

        # Check batch state was set to fixing
        batches = millpy_fix._status.read_batches(status_path)
        batch_state = next((b for b in batches if b["name"] == "test-batch"), None)
        self.assertIsNotNone(batch_state)
        self.assertEqual(batch_state.get("state"), "fixing")

        # Check resume=False was passed
        self.assertFalse(captured["resume"], "resume must be False for fixer dispatch")

        # Check prompt contains absolute review file path
        self.assertIn(str(self.review_file), captured["prompt_text"])

    def test_batch_missing_batch_name(self):
        """Batch scope without --batch-name -> exit 1, stdout empty."""
        rc, out = self._run_main([
            "--scope", "batch",
            "--review-file", str(self.review_file),
        ])
        self.assertEqual(rc, 1)
        self.assertEqual(out.strip(), "")

    def test_batch_unknown_batch_name(self):
        """Batch scope with nonexistent batch name -> exit 1, stdout empty."""
        rc, out = self._run_main([
            "--scope", "batch",
            "--batch-name", "nonexistent",
            "--review-file", str(self.review_file),
        ])
        self.assertEqual(rc, 1)
        self.assertEqual(out.strip(), "")

    def test_holistic_happy_path(self):
        """Holistic scope -> success JSON, holistic-fixing in timeline, no BATCH_SESSION_IDS."""
        status_path = self.tmp_path / "_mill" / "status.md"

        captured = {}

        def mock_run(prompt_text, *, model, effort, session_id, resume, cwd, timeout):
            captured["prompt_text"] = prompt_text
            captured["resume"] = resume
            return ('{"status":"success","commit_sha":"abc","session_id":"fake"}\n', "fake-session")

        with unittest.mock.patch.object(
            millpy_fix._implementer_claude, "run",
            side_effect=mock_run,
        ):
            rc, out = self._run_main([
                "--scope", "holistic",
                "--review-file", str(self.review_file),
                "--round", "1",
            ])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "success")

        # Check that holistic-fixing was appended to timeline
        full = millpy_fix._status.read_full(status_path)
        self.assertTrue(
            any(e.startswith("holistic-fixing") for e in full["timeline"]),
            f"Expected holistic-fixing in timeline, got: {full['timeline']}",
        )

        # Check resume=False was passed
        self.assertFalse(captured["resume"], "resume must be False for fixer dispatch")

        # Check that BATCH_SESSION_IDS is NOT in the prompt (removed deliberately)
        self.assertNotIn("BATCH_SESSION_IDS", captured["prompt_text"])

        # Check that batch file path IS in the prompt
        expected_batch_path = str(self.tmp_path / "_mill" / "plan" / "01-test-batch.md")
        self.assertIn(expected_batch_path, captured["prompt_text"])

    def test_holistic_missing_review_file_flag(self):
        """Holistic scope without --review-file -> exit 1, stdout empty."""
        rc, out = self._run_main([
            "--scope", "holistic",
        ])
        self.assertEqual(rc, 1)
        self.assertEqual(out.strip(), "")

    def test_review_file_not_found(self):
        """Both scopes when review file doesn't exist -> exit 1, stdout empty."""
        # Test batch scope
        rc, out = self._run_main([
            "--scope", "batch",
            "--batch-name", "test-batch",
            "--review-file", "nonexistent.md",
        ])
        self.assertEqual(rc, 1)
        self.assertEqual(out.strip(), "")

        # Test holistic scope
        rc, out = self._run_main([
            "--scope", "holistic",
            "--review-file", "nonexistent.md",
        ])
        self.assertEqual(rc, 1)
        self.assertEqual(out.strip(), "")

    def test_llm_error_propagates_as_stuck_transient(self):
        """LLMError from fixer -> stuck/transient JSON on stdout, exit 1."""
        with unittest.mock.patch.object(
            millpy_fix._implementer_claude, "run",
            side_effect=millpy_fix._llm_claude.LLMError("timeout"),
        ):
            rc, out = self._run_main([
                "--scope", "batch",
                "--batch-name", "test-batch",
                "--review-file", str(self.review_file),
            ])

        self.assertEqual(rc, 1)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "transient")

    def test_implementer_no_json_emits_stuck_logic(self):
        """Fixer output with no valid JSON -> stuck/logic JSON, exit 0."""
        with unittest.mock.patch.object(
            millpy_fix._implementer_claude, "run",
            return_value=("no json here\n", "sess"),
        ):
            rc, out = self._run_main([
                "--scope", "batch",
                "--batch-name", "test-batch",
                "--review-file", str(self.review_file),
            ])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "logic")

    def test_resume_false_always_passed(self):
        """Regression guard: both batch and holistic pass resume=False."""
        resume_values = []

        def capture_resume(prompt_text, *, model, effort, session_id, resume, cwd, timeout):
            resume_values.append(resume)
            return ('{"status":"success","commit_sha":"abc","session_id":"fake"}\n', "fake")

        with unittest.mock.patch.object(
            millpy_fix._implementer_claude, "run",
            side_effect=capture_resume,
        ):
            # Test batch scope
            rc, _ = self._run_main([
                "--scope", "batch",
                "--batch-name", "test-batch",
                "--review-file", str(self.review_file),
            ])
            self.assertEqual(rc, 0)

        # Reset for holistic test
        resume_values.clear()

        with unittest.mock.patch.object(
            millpy_fix._implementer_claude, "run",
            side_effect=capture_resume,
        ):
            # Test holistic scope
            rc, _ = self._run_main([
                "--scope", "holistic",
                "--review-file", str(self.review_file),
            ])
            self.assertEqual(rc, 0)

        # Verify both passed resume=False
        self.assertEqual(resume_values, [False, False])


if __name__ == "__main__":
    unittest.main()
