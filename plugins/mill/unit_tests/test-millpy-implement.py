"""Unit tests for millpy-implement.py CLI main().

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

import _implementer_common  # noqa: E402
import _safe_rmtree  # noqa: E402

_IMPLEMENT_PATH = HUB / "plugins" / "mill" / "scripts" / "millpy-implement.py"

_spec = importlib.util.spec_from_file_location("millpy_implement", str(_IMPLEMENT_PATH))
millpy_implement = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(millpy_implement)


def _make_fixture(tmp_path: Path) -> None:
    """Create the fake worktree directory tree in tmp_path."""
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


class TestMillpyImplement(unittest.TestCase):

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())
        self.addCleanup(_safe_rmtree.safe_rmtree, self.tmp_path, allowed_root=self.tmp_path, ignore_errors=True)

        _make_fixture(self.tmp_path)

        self.original_cwd = os.getcwd()
        os.chdir(self.tmp_path)
        self.addCleanup(os.chdir, self.original_cwd)

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
                "roles": {"implementer": {"self_fix_rounds": 2, "model": "sonnethigh"}},
                "llm": {"implementer_timeout": 1800},
            },
        )
        self.mock_slug_from_branch = _p(
            millpy_implement._marker, "slug_from_branch",
            return_value="test-slug",
        )
        self.mock_read_branch = _p(
            millpy_implement._status, "read_branch",
            return_value="test-branch",
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

    def _run_main(self, argv):
        """Run main(argv) with stdout captured. Returns (rc, captured_stdout)."""
        buf = io.StringIO()
        with unittest.mock.patch("sys.stdout", buf):
            rc = millpy_implement.main(argv)
        return rc, buf.getvalue()

    def test_1_initial_dispatch_success(self):
        """Initial dispatch: pending batch -> success JSON, batch state running."""
        status_path = self.tmp_path / "task" / "status.md"

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                "fake-session",
            ),
        ):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "success")

        batches = millpy_implement._status.read_batches(status_path)
        self.assertEqual(batches[0]["state"], "running")
        self.assertEqual(batches[0]["implementer_session"], "00000000-0000-0000-0000-000000000001")

    def test_2_initial_dispatch_running_batch(self):
        """Crash-recovery: batch already running -> re-dispatches with new UUID."""
        status_path = self.tmp_path / "task" / "status.md"
        millpy_implement._status.set_batch_field(status_path, "test-batch", "state", "running")

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                "fake-session",
            ),
        ):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        batches = millpy_implement._status.read_batches(status_path)
        self.assertEqual(batches[0]["state"], "running")
        self.assertEqual(batches[0]["implementer_session"], "00000000-0000-0000-0000-000000000001")

    def test_3_initial_dispatch_stuck(self):
        """Initial dispatch: implementer returns stuck -> exit 0, stuck JSON."""
        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"stuck","stuck_type":"verify","reason":"tests failed"}\n',
                "fake-session",
            ),
        ):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")

    def test_6_batch_not_found(self):
        """Unknown batch name -> exit 1, no JSON on stdout."""
        rc, out = self._run_main(["nonexistent-batch"])
        self.assertEqual(rc, 1)
        self.assertEqual(out.strip(), "")

    def test_7_malformed_json_from_implementer(self):
        """Implementer output with no valid JSON -> exit 0, stuck/logic JSON."""
        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=("implementer output with no json\n", "sess"),
        ):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "logic")

    def test_9_model_and_effort_from_config(self):
        """Initial dispatch: model and effort read from config and passed to implementer."""
        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                "fake-session",
            ),
        ) as mock_run:
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        call_kwargs = mock_run.call_args.kwargs
        self.assertEqual(call_kwargs.get("model"), "claude-sonnet-4-6")
        self.assertEqual(call_kwargs.get("effort"), "high")

    def test_10_model_default_fallback(self):
        """When roles.implementer.model is absent, defaults to 'sonnethigh'."""
        self.mock_load_config.return_value = {
            "paths": {"status_md": "_mill/status.md"},
            "roles": {"implementer": {"self_fix_rounds": 2}},
            "llm": {"implementer_timeout": 1800},
        }
        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                "fake-session",
            ),
        ):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        # _reviewers.resolve was called with 'sonnethigh' (the default)
        self.mock_reviewers_resolve.assert_called_with(
            self.mock_reviewers_load.return_value, "sonnethigh"
        )

    def test_11_brief_size_guard_fires(self):
        """Brief exceeds max_implementer_prompt_chars -> stuck/transient, no LLM call."""
        self.mock_load_config.return_value = {
            "paths": {"status_md": "_mill/status.md"},
            "roles": {"implementer": {"self_fix_rounds": 2, "model": "haiku"}},
            "llm": {"implementer_timeout": 1800, "max_implementer_prompt_chars": 10},
        }
        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="x" * 20):
            with unittest.mock.patch.object(millpy_implement._implementer_claude, "run") as mock_run:
                rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "transient")
        self.assertIn("max_implementer_prompt_chars", data["reason"])
        mock_run.assert_not_called()

    def test_12_brief_size_guard_disabled(self):
        """max_implementer_prompt_chars = 0 (disabled) -> guard does not fire."""
        self.mock_load_config.return_value = {
            "paths": {"status_md": "_mill/status.md"},
            "roles": {"implementer": {"self_fix_rounds": 2, "model": "haiku"}},
            "llm": {"implementer_timeout": 1800, "max_implementer_prompt_chars": 0},
        }
        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="x" * 20):
            with unittest.mock.patch.object(
                millpy_implement._implementer_claude, "run",
                return_value=(
                    '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                    "fake-session",
                ),
            ) as mock_run:
                rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        # Verify that _implementer_claude.run was called (the guard did not fire)
        mock_run.assert_called_once()


class TestForwardOutput(unittest.TestCase):

    def _call(self, output: str) -> tuple[int, str]:
        buf = io.StringIO()
        with unittest.mock.patch.object(
            _implementer_common._subprocess_util, "run",
            return_value=unittest.mock.MagicMock(returncode=1, stdout=""),
        ):
            with unittest.mock.patch.object(
                _implementer_common._cleanliness, "compute_scope_violations",
                return_value=[],
            ):
                with unittest.mock.patch("sys.stdout", buf):
                    rc = millpy_implement._forward_output(output, Path("/fake"))
        return rc, buf.getvalue()

    def test_fo_1_bare_json_on_last_line(self):
        """Bare JSON with status key on last line -> printed verbatim, exit 0."""
        json_str = '{"status":"success","commit_sha":"abc"}'
        rc, out = self._call(f"some preamble\n{json_str}")
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.strip()), json.loads(json_str))

    def test_fo_2_json_in_fence(self):
        """JSON inside ```json fence -> extracted and printed, exit 0."""
        json_str = '{"status":"success","commit_sha":"abc"}'
        output = f"```json\n{json_str}\n```"
        rc, out = self._call(output)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.strip()), json.loads(json_str))

    def test_fo_3_json_in_fence_trailing_blank_lines(self):
        """JSON in fence with trailing blank lines -> extracted correctly, exit 0."""
        json_str = '{"status":"success","commit_sha":"abc"}'
        output = f"```json\n{json_str}\n```\n\n\n"
        rc, out = self._call(output)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.strip()), json.loads(json_str))

    def test_fo_4_multiple_json_lines_last_wins(self):
        """Multiple lines with status JSON -> last one printed."""
        first = '{"status":"stuck","stuck_type":"verify","reason":"oops"}'
        last = '{"status":"success","commit_sha":"def"}'
        rc, out = self._call(f"{first}\n{last}")
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.strip()), json.loads(last))

    def test_fo_5_no_json_anywhere(self):
        """No JSON-like pattern in output -> stuck/logic sentinel printed, exit 0."""
        rc, out = self._call("implementer ran but produced no report")
        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "logic")
        self.assertIn("no structured report", data["reason"])

    def test_fo_6_malformed_json_last_valid_earlier(self):
        """Unclosed brace last (regex miss) + valid JSON earlier -> earlier valid one printed."""
        valid = '{"status":"success","commit_sha":"x"}'
        output = f'{valid}\n{{"status":"broken"'
        rc, out = self._call(output)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.strip()), json.loads(valid))

    def test_fo_7_sha_normalized(self):
        """git rev-parse success -> commit_sha in output replaced with HEAD sha."""
        sha = "a" * 40
        buf = io.StringIO()
        with unittest.mock.patch.object(
            _implementer_common._subprocess_util, "run",
            return_value=unittest.mock.MagicMock(returncode=0, stdout=sha + "\n"),
        ):
            with unittest.mock.patch.object(
                _implementer_common._cleanliness, "compute_scope_violations",
                return_value=[],
            ):
                with unittest.mock.patch("sys.stdout", buf):
                    rc = millpy_implement._forward_output(
                        '{"status":"success","commit_sha":"abc1234","session_id":"x"}',
                        Path("/fake"),
                    )
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(buf.getvalue().strip())["commit_sha"], sha)

    def test_fo_8_sha_git_failure(self):
        """git rev-parse failure -> original commit_sha preserved in output."""
        buf = io.StringIO()
        with unittest.mock.patch.object(
            _implementer_common._subprocess_util, "run",
            return_value=unittest.mock.MagicMock(returncode=1, stdout=""),
        ):
            with unittest.mock.patch.object(
                _implementer_common._cleanliness, "compute_scope_violations",
                return_value=[],
            ):
                with unittest.mock.patch("sys.stdout", buf):
                    rc = millpy_implement._forward_output(
                        '{"status":"success","commit_sha":"abc1234","session_id":"x"}',
                        Path("/fake"),
                    )
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(buf.getvalue().strip())["commit_sha"], "abc1234")


if __name__ == "__main__":
    unittest.main()
