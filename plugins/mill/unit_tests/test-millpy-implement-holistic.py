"""Unit tests for millpy-implement-holistic.py CLI main().

Loads the module under test via importlib and calls main(argv) in-process.
All external I/O (git, LLM, path resolution) is patched in setUp.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
import uuid
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

_IMPLEMENT_HOLISTIC_PATH = (
    HUB / "plugins" / "mill" / "scripts" / "millpy-implement-holistic.py"
)

_spec = importlib.util.spec_from_file_location(
    "millpy_implement_holistic", str(_IMPLEMENT_HOLISTIC_PATH)
)
millpy_implement_holistic = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(millpy_implement_holistic)


def _make_fixture(tmp_path: Path) -> Path:
    """Create the fake worktree directory tree in tmp_path.

    Returns the review file path.
    """
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
        "roles:\n  implementer:\n    self_fix_rounds: 2\n",
        encoding="utf-8",
    )

    reviews_dir = tmp_path / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    review_file = reviews_dir / "holistic-review.md"
    review_file.write_text("# Holistic Review\nsome findings here\n", encoding="utf-8")

    return review_file


class TestMillpyImplementHolistic(unittest.TestCase):

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp_path, ignore_errors=True)

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
            millpy_implement_holistic._paths, "resolve_git_root",
            return_value=self.tmp_path,
        )
        self.mock_resolve_wiki = _p(
            millpy_implement_holistic._paths, "resolve_wiki_path",
            return_value=self.tmp_path / "wiki",
        )
        self.mock_load_config = _p(
            millpy_implement_holistic._review_common, "load_config",
            return_value={
                "paths": {"status_md": "_mill/status.md"},
                "roles": {"implementer": {"self_fix_rounds": 2}},
                "llm": {"implementer_timeout": 1800},
            },
        )
        self.mock_slug_from_branch = _p(
            millpy_implement_holistic._marker, "slug_from_branch",
            return_value="test-slug",
        )
        self.mock_read_branch = _p(
            millpy_implement_holistic._status, "read_branch",
            return_value="test-branch",
        )
        self.mock_subprocess_run = _p(
            millpy_implement_holistic._subprocess_util, "run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="abc1234\n", stderr=""
            ),
        )
        self.mock_uuid4 = _p(
            millpy_implement_holistic.uuid, "uuid4",
            return_value=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        )

    def _run_main(self, argv):
        """Run main(argv) with stdout captured. Returns (rc, captured_stdout)."""
        buf = io.StringIO()
        with unittest.mock.patch("sys.stdout", buf):
            rc = millpy_implement_holistic.main(argv)
        return rc, buf.getvalue()

    def test_1_fresh_dispatch_success(self):
        """Fresh dispatch: review file supplied -> success JSON, holistic-fixing in timeline."""
        status_path = self.tmp_path / "task" / "status.md"

        with unittest.mock.patch.object(
            millpy_implement_holistic._implementer_sonnet, "run",
            return_value=(
                '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                "fake-session",
            ),
        ):
            rc, out = self._run_main(["--review-file", str(self.review_file)])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "success")

        full = millpy_implement_holistic._status.read_full(status_path)
        self.assertTrue(
            any(e.startswith("holistic-fixing") for e in full["timeline"]),
            f"Expected holistic-fixing in timeline, got: {full['timeline']}",
        )

    def test_2_llm_error(self):
        """LLMError from implementer -> stuck/transient JSON on stdout, exit 1."""
        with unittest.mock.patch.object(
            millpy_implement_holistic._implementer_sonnet, "run",
            side_effect=millpy_implement_holistic._llm_claude.LLMError("timeout"),
        ):
            rc, out = self._run_main(["--review-file", str(self.review_file)])

        self.assertEqual(rc, 1)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "transient")

    def test_3_no_json_from_implementer(self):
        """Implementer output with no valid JSON -> stuck/logic JSON, exit 0."""
        with unittest.mock.patch.object(
            millpy_implement_holistic._implementer_sonnet, "run",
            return_value=("no json here\n", "sess"),
        ):
            rc, out = self._run_main(["--review-file", str(self.review_file)])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "logic")

    def test_4_missing_review_file_flag(self):
        """No --review-file flag -> exit 1, stdout empty."""
        rc, out = self._run_main([])
        self.assertEqual(rc, 1)
        self.assertEqual(out.strip(), "")

    def test_5_review_file_not_found(self):
        """--review-file points to nonexistent path -> exit 1, stdout empty."""
        rc, out = self._run_main(["--review-file", "nonexistent.md"])
        self.assertEqual(rc, 1)
        self.assertEqual(out.strip(), "")

    def test_6_batch_files_and_session_ids_injected(self):
        """prompt_text contains absolute batch file path and test-batch: (none)."""
        captured = {}

        def mock_run(prompt_text, *, session_id, resume, cwd, timeout):
            captured["prompt_text"] = prompt_text
            return ('{"status":"success","commit_sha":"abc","session_id":"fake"}\n', "fake")

        with unittest.mock.patch.object(
            millpy_implement_holistic._implementer_sonnet, "run",
            side_effect=mock_run,
        ):
            rc, _ = self._run_main(["--review-file", str(self.review_file)])

        self.assertEqual(rc, 0)
        prompt_text = captured["prompt_text"]

        expected_batch_path = str(self.tmp_path / "task" / "plan" / "01-test-batch.md")
        self.assertIn(
            expected_batch_path, prompt_text,
            f"Expected batch file path {expected_batch_path!r} in prompt_text",
        )
        self.assertIn(
            "test-batch: (none)", prompt_text,
            "Expected 'test-batch: (none)' in prompt_text (no implementer_session in fixture)",
        )


if __name__ == "__main__":
    unittest.main()
