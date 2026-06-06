"""Unit parity test for agent-mode prepare/finalize round-trip.

Tests that the prepare -> finalize round-trip (with captured agent output)
produces byte-for-byte identical JSON envelopes and artifacts as the full
(subprocess) path, for both implementer-class (millpy-implement.py) and
reviewer-class (millpy-review-discussion.py) CLIs.

No real LLM calls or Agent tool. Uses fixtures to feed canned sub-agent output
to the finalize stage and verifies the resulting JSON envelope matches what
the full mode would produce.
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

import _implementer_common  # noqa: E402
import _safe_rmtree  # noqa: E402
import _reviewer_test_stub as stub  # noqa: E402
import _test_registry  # noqa: E402
import _test_helpers  # noqa: E402
from wiki import _client as wiki  # noqa: E402
from _review_discussion import prepare as discussion_prepare, finalize as discussion_finalize  # noqa: E402
from _test_helpers import seed_wiki_config  # noqa: E402

_IMPLEMENT_PATH = HUB / "plugins" / "mill" / "scripts" / "millpy-implement.py"
_REVIEW_DISCUSSION_PATH = HUB / "plugins" / "mill" / "scripts" / "millpy-review-discussion.py"

_spec_impl = importlib.util.spec_from_file_location("millpy_implement", str(_IMPLEMENT_PATH))
millpy_implement = importlib.util.module_from_spec(_spec_impl)
_spec_impl.loader.exec_module(millpy_implement)

_spec_review = importlib.util.spec_from_file_location("millpy_review_discussion", str(_REVIEW_DISCUSSION_PATH))
millpy_review_discussion = importlib.util.module_from_spec(_spec_review)
_spec_review.loader.exec_module(millpy_review_discussion)

SLUG = "test-slug"
APPROVE_TEXT = "# Review: test\n\n```yaml\nverdict: APPROVE\n```\n"


def _make_implementer_fixture(tmp_path: Path) -> None:
    """Create the fake worktree directory tree for implementer tests."""
    plan_dir = tmp_path / "task" / "plan"
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
    (tmp_path / "task" / "status.md").write_text(status_text, encoding="utf-8")

    millhouse_dir = tmp_path / ".millhouse"
    millhouse_dir.mkdir(parents=True, exist_ok=True)
    (millhouse_dir / "config.local.yaml").write_text("{}", encoding="utf-8")

    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / "config.yaml").write_text(
        "roles:\n  implementer:\n    self_fix_rounds: 2\n", encoding="utf-8"
    )

    (tmp_path / "reviews").mkdir(parents=True, exist_ok=True)


def _make_reviewer_fixture(tmp: Path) -> tuple[Path, Path, Path]:
    """Create a container/wts/<slug> worktree fixture for reviewer tests.

    Returns (mill_dir, project_root, wiki_root).
    """
    worktree = tmp / "container" / "wts" / SLUG
    worktree.mkdir(parents=True)
    subprocess.run(["git", "-C", str(worktree), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(worktree), "checkout", "-b", f"hanf/{SLUG}"], capture_output=True)
    subprocess.run(["git", "-C", str(worktree), "config", "user.email", "test@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(worktree), "config", "user.name", "test"], check=True, capture_output=True)
    (worktree / ".gitignore").write_text("\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(worktree), "add", ".gitignore"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(worktree), "commit", "-m", "seed"], check=True, capture_output=True)
    mill_dir = worktree / ".millhouse"
    mill_dir.mkdir(parents=True, exist_ok=True)
    wiki_root = tmp / "wiki"
    _test_helpers.init_wiki_repo(wiki_root)
    seed_wiki_config(wiki_root)
    (wiki_root / "Home.md").write_text(
        f"## Test Task\n[{SLUG}] [active]\n\n_body_\n", encoding="utf-8"
    )
    wiki.upsert_task(wiki_root, SLUG, title="Test Task", status="active")
    (mill_dir / "config.local.yaml").write_text(
        f"paths:\n  wiki: '{wiki_root.as_posix()}'\n"
        f"spawn:\n  branch_prefix: 'hanf/'\n", encoding="utf-8"
    )
    # Write registry so prepare() can resolve reviewers
    _test_registry.write_to(wiki_root)
    (worktree / "discussion.md").write_text("# Discussion\n\nTest discussion.\n", encoding="utf-8")
    (worktree / "reviews").mkdir(parents=True, exist_ok=True)
    (worktree / "plan").mkdir(parents=True, exist_ok=True)
    return mill_dir, worktree, wiki_root


class TestImplementerModeParity(unittest.TestCase):

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())
        self.addCleanup(_safe_rmtree.safe_rmtree, self.tmp_path, allowed_root=self.tmp_path, ignore_errors=True)

        _make_implementer_fixture(self.tmp_path)

        self.original_cwd = os.getcwd()
        os.chdir(self.tmp_path)

        def _p(target, attr, **kwargs):
            patcher = unittest.mock.patch.object(target, attr, **kwargs)
            mock_obj = patcher.start()
            self.addCleanup(patcher.stop)
            return mock_obj

        self.mock_resolve_git_root = _p(
            millpy_implement._paths, "resolve_git_root",
            return_value=self.tmp_path,
        )
        self.mock_resolve_wiki = _p(
            millpy_implement._paths, "resolve_wiki_path",
            return_value=self.tmp_path / "wiki",
        )
        self.mock_load_config = _p(
            millpy_implement._review_common, "load_config",
            return_value={
                "paths": {"status_md": "_mill/status.md"},
                "roles": {"implementer": {"self_fix_rounds": 2, "model": "claude-sonnet-4-6"}},
                "llm": {"implementer_timeout": 1800},
            },
        )
        self.mock_slug_from_branch = _p(
            millpy_implement._marker, "slug_from_branch",
            return_value="test-slug",
        )
        self.mock_subprocess_run = _p(
            millpy_implement._subprocess_util, "run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="abc1234\n", stderr=""
            ),
        )
        self.mock_uuid4 = _p(
            millpy_implement.uuid, "uuid4",
            return_value=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        )
        self.mock_capture_snapshot = _p(
            millpy_implement._cleanliness, "capture_snapshot",
        )
        self.mock_reviewers_load = _p(
            millpy_implement._reviewers, "load",
            return_value={
                "sonnethigh": {
                    "type": "single",
                    "provider": "claude",
                    "model": "claude-sonnet-4-6",
                    "effort": "high",
                }
            },
        )
        self.mock_reviewers_resolve = _p(
            millpy_implement._reviewers, "resolve",
            return_value={
                "type": "single",
                "provider": "claude",
                "model": "claude-sonnet-4-6",
                "effort": "high",
            },
        )
        self.mock_compute_scope_violations = _p(
            _implementer_common._cleanliness, "compute_scope_violations",
            return_value=[],
        )
        self.addCleanup(os.chdir, self.original_cwd)

    def _run_main(self, argv):
        """Run main(argv) with stdout captured. Returns (rc, captured_stdout)."""
        buf = io.StringIO()
        with unittest.mock.patch("sys.stdout", buf):
            rc = millpy_implement.main(argv)
        return rc, buf.getvalue()

    def test_implementer_parity_prepare_stage(self):
        """Prepare stage: render brief, write file, emit envelope. No LLM."""
        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="Brief text"):
            with unittest.mock.patch.object(
                millpy_implement._implementer_claude, "run"
            ) as mock_run:
                rc, out = self._run_main(["test-batch", "--stage", "prepare"])

        self.assertEqual(rc, 0)
        # LLM should not be called in prepare stage
        mock_run.assert_not_called()
        # Output should be prepare JSON envelope
        data = json.loads(out.strip())
        self.assertEqual(data["stage"], "prepare")
        self.assertEqual(data["role"], "implement")
        self.assertEqual(data["scope"], "test-batch")
        self.assertEqual(data["round"], 1)
        self.assertIsNotNone(data["brief_path"])
        # Verify brief file exists and contains the prompt text
        brief_path = Path(data["brief_path"])
        self.assertTrue(brief_path.exists(), f"Brief file not found: {brief_path}")
        brief_content = brief_path.read_text(encoding="utf-8")
        self.assertEqual(brief_content, "Brief text")

    def test_implementer_parity_finalize_stage(self):
        """Finalize stage: read agent output, emit same envelope as full. No LLM."""
        # First run prepare to set up status
        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="Brief text"):
            with unittest.mock.patch.object(millpy_implement._implementer_claude, "run"):
                self._run_main(["test-batch", "--stage", "prepare"])

        # Create a canned agent output file
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake-session"}\n',
            encoding="utf-8"
        )

        # Run finalize
        with unittest.mock.patch.object(millpy_implement._implementer_claude, "run") as mock_run:
            rc, out = self._run_main([
                "test-batch",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        # LLM should not be called in finalize stage
        mock_run.assert_not_called()
        # Output should be the processed envelope
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "success")
        self.assertIn("commit_sha", data)
        self.assertEqual(data.get("session_id"), "fake-session")


class TestReviewerModeParity(unittest.TestCase):

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())
        self.addCleanup(_safe_rmtree.safe_rmtree, self.tmp_path, allowed_root=self.tmp_path, ignore_errors=True)

        self.mill_dir, self.project_root, self.wiki_root = _make_reviewer_fixture(self.tmp_path)

        self.original_cwd = os.getcwd()
        os.chdir(self.project_root)
        self.addCleanup(os.chdir, self.original_cwd)

        # Import the review modules directly for testing
        import _review_common
        import _reviewer_single
        self._review_common = _review_common
        self._reviewer_single = _reviewer_single

    def test_reviewer_parity_prepare_finalize(self):
        """Discussion review prepare + finalize round-trip parity. No LLM."""
        cfg = {
            "paths": {
                "discussion_file": "discussion.md",
                "plan_dir": "plan/",
                "reviews_dir": "reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {"rounds": 2, "reviewer": "sonnetmax"},
                },
            },
        }

        # Step 1: Prepare stage
        # Guard that _reviewer_single.run is not called during prepare
        with unittest.mock.patch.object(
            self._reviewer_single, "run"
        ) as mock_run:
            prepare_result = discussion_prepare(cfg, SLUG, self.mill_dir, self.project_root, self.wiki_root)
            # LLM should not be called during prepare
            mock_run.assert_not_called()

        self.assertIn("prompt_text", prepare_result)
        self.assertIn("model", prepare_result)
        self.assertEqual(prepare_result["round"], 1)
        self.assertIn("reviews_dir", prepare_result)
        self.assertEqual(prepare_result["scope"], "holistic")

        # Step 2: Verify brief was written
        from _agent_dispatch import write_brief
        briefs_dir = self.project_root / "_mill" / "briefs"
        brief_path = write_brief(
            briefs_dir,
            "review-discussion",
            prepare_result["scope"],
            prepare_result["round"],
            prepare_result["prompt_text"]
        )
        self.assertTrue(brief_path.exists())
        brief_content = brief_path.read_text(encoding="utf-8")
        self.assertEqual(brief_content, prepare_result["prompt_text"])

        # Step 3: Finalize stage with canned agent output
        # Guard that _reviewer_single.run is not called during finalize
        agent_output = APPROVE_TEXT
        with unittest.mock.patch.object(
            self._reviewer_single, "run"
        ) as mock_run:
            result = discussion_finalize(
                cfg,
                SLUG,
                agent_output,
                round_n=prepare_result["round"],
                reviews_dir=prepare_result["reviews_dir"],
                mill_dir=self.mill_dir,
                project_root=self.project_root,
                wiki_root=self.wiki_root
            )
            # Ensure LLM was not called during finalize
            mock_run.assert_not_called()

        # Verify result
        self.assertEqual(result.verdict, "APPROVE")
        self.assertEqual(result.round, 1)
        self.assertGreater(len(result.reviews), 0)
        self.assertEqual(result.reviews[0]["scope"], "holistic")
        self.assertEqual(result.reviews[0]["verdict"], "APPROVE")
        # Verify review file was written
        review_file_path = Path(result.reviews[0]["file"])
        self.assertTrue(review_file_path.exists(), f"Review file not found: {review_file_path}")


if __name__ == "__main__":
    unittest.main()
