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
        self.mock_resolve_hub_path = _p(
            millpy_implement._paths, "resolve_hub_path",
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

        # Route rev-parse HEAD to differ between the start_sha capture (first call)
        # and the post-implementation HEAD, so the no-content-commit guard in
        # _forward_output sees HEAD != start_sha and accepts the success report.
        rev_parse_calls = []

        def routing_fn(argv, **kw):
            if argv[1] == "rev-parse":
                rev_parse_calls.append(1)
                sha = "start000" if len(rev_parse_calls) == 1 else "end11111"
                return subprocess.CompletedProcess(args=argv, returncode=0, stdout=sha + "\n", stderr="")
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")

        self.mock_subprocess_run.side_effect = routing_fn

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

    def test_13_stage_prepare_emits_brief_and_envelope(self):
        """--stage prepare: renders brief, calls emit_prepare, no LLM call."""
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
        self.assertTrue(data["brief_path"])

    def test_14_stage_finalize_reads_agent_output(self):
        """--stage finalize: reads agent output file, calls finalize_from_output."""
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8"
        )

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run"
        ) as mock_run:
            rc, out = self._run_main([
                "test-batch",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        # LLM should not be called in finalize stage
        mock_run.assert_not_called()
        # Output should be the agent output processed by _forward_output
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "success")

    def test_commits_made_nonzero_on_llm_error(self):
        """LLMError with commits made: rev-list returns 3 -> stuck JSON includes commits_made=3."""
        def routing_fn(argv, **kw):
            if argv[1] == "rev-list":
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout="3\n", stderr=""
                )
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")

        self.mock_subprocess_run.side_effect = routing_fn

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            side_effect=millpy_implement._llm_claude.LLMError("timeout"),
        ):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 1)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "transient")
        self.assertEqual(data["commits_made"], 3)

    def test_commits_made_zero_on_llm_error_no_commits(self):
        """LLMError with no commits made: rev-list returns 0 -> stuck JSON includes commits_made=0."""
        def routing_fn(argv, **kw):
            if argv[1] == "rev-list":
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout="0\n", stderr=""
                )
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")

        self.mock_subprocess_run.side_effect = routing_fn

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            side_effect=millpy_implement._llm_claude.LLMError("timeout"),
        ):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 1)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "transient")
        self.assertEqual(data["commits_made"], 0)

    def test_commits_made_zero_on_rev_list_failure(self):
        """LLMError with rev-list failure: returncode=1 -> commits_made defaults to 0."""
        def routing_fn(argv, **kw):
            if argv[1] == "rev-list":
                return subprocess.CompletedProcess(
                    args=argv, returncode=1, stdout="", stderr="error"
                )
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")

        self.mock_subprocess_run.side_effect = routing_fn

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            side_effect=millpy_implement._llm_claude.LLMError("timeout"),
        ):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 1)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "transient")
        self.assertEqual(data["commits_made"], 0)

    def test_skip_start_commit_on_refire(self):
        """Re-fire with matching last commit: start-batch commit block is skipped."""
        batch_name = "test-batch"

        def routing_fn(argv, **kw):
            if argv[1] == "log":
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout=f"mill-go: start batch {batch_name}\n", stderr=""
                )
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")

        self.mock_subprocess_run.side_effect = routing_fn

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                "fake-session",
            ),
        ) as mock_impl_run:
            with unittest.mock.patch.object(
                millpy_implement._subprocess_util, "git_commit"
            ) as mock_git_commit:
                rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        # git_commit should NOT be called
        mock_git_commit.assert_not_called()
        # But _implementer_claude.run should still be called
        mock_impl_run.assert_called_once()

    def test_no_skip_start_commit_on_fresh_fire(self):
        """Fresh fire with different last commit: start-batch commit block is executed."""
        def routing_fn(argv, **kw):
            if argv[1] == "log":
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout="some other commit message\n", stderr=""
                )
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")

        self.mock_subprocess_run.side_effect = routing_fn

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                "fake-session",
            ),
        ):
            with unittest.mock.patch.object(
                millpy_implement._subprocess_util, "git_commit",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ) as mock_git_commit:
                rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        # git_commit should be called exactly once
        mock_git_commit.assert_called_once()

    def test_15_stage_finalize_accepts_session_and_start_sha_flags(self):
        """--stage finalize accepts --session-id and --start-sha flags, still uses status.md values."""
        status_path = self.tmp_path / "task" / "status.md"
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8"
        )

        # Set distinct sentinel values in status.md
        millpy_implement._status.set_batch_field(status_path, "test-batch", "start_sha", "STATUS_SHA")
        millpy_implement._status.set_batch_field(status_path, "test-batch", "implementer_session", "STATUS_SESSION")

        # Patch finalize_from_output to capture the call
        with unittest.mock.patch.object(
            millpy_implement, "finalize_from_output",
            return_value=0
        ) as mock_finalize:
            rc, out = self._run_main([
                "test-batch",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
                "--session-id", "CLI_SESSION",
                "--start-sha", "CLI_SHA",
            ])

        # Verify argparse succeeded (rc == 0)
        self.assertEqual(rc, 0)

        # Verify finalize_from_output was called once
        mock_finalize.assert_called_once()

        # Verify the kwargs passed to finalize_from_output contain status.md values, NOT CLI args
        call_kwargs = mock_finalize.call_args.kwargs
        self.assertEqual(call_kwargs.get("start_sha"), "STATUS_SHA")
        self.assertEqual(call_kwargs.get("session_id"), "STATUS_SESSION")

    def test_finalize_stage_resolves_batch_verify_command(self):
        """--stage finalize: batch verify command is resolved and passed to finalize_from_output."""
        # Update the batch file to include a verify command in frontmatter
        plan_dir = self.tmp_path / "task" / "plan"
        batch_file = plan_dir / "01-test-batch.md"
        batch_file.write_text(
            "```yaml\n"
            "task: Test Task\n"
            "verify: exit 0\n"
            "```\n\n"
            "# Batch: test-batch\n",
            encoding="utf-8"
        )

        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8"
        )

        # Patch finalize_from_output to capture the verify_cmd argument
        with unittest.mock.patch.object(
            millpy_implement, "finalize_from_output",
            return_value=0,
        ) as mock_finalize:
            rc, out = self._run_main([
                "test-batch",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        # Verify that finalize_from_output was called with the resolved verify_cmd
        mock_finalize.assert_called_once()
        call_kwargs = mock_finalize.call_args.kwargs
        self.assertEqual(call_kwargs.get("verify_cmd"), "exit 0")

    def test_overview_verify_threaded_as_module_wide(self):
        """Overview with non-null top-level verify: threads it as module_wide_verify_cmd."""
        plan_dir = self.tmp_path / "task" / "plan"
        # Write an overview with a non-null top-level verify command
        overview_with_verify = (
            "# Plan: Test Task\n\n"
            "```yaml\n"
            "task: Test Task\n"
            "slug: test-slug\n"
            "approved: true\n"
            "verify: exit 0\n"
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
        (plan_dir / "00-overview.md").write_text(overview_with_verify, encoding="utf-8")

        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8"
        )

        with unittest.mock.patch.object(
            millpy_implement, "finalize_from_output",
            return_value=0,
        ) as mock_finalize:
            rc, out = self._run_main([
                "test-batch",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        mock_finalize.assert_called_once()
        call_kwargs = mock_finalize.call_args.kwargs
        # The overview-level verify command must be threaded as module_wide_verify_cmd
        self.assertEqual(call_kwargs.get("module_wide_verify_cmd"), "exit 0")

    def test_overview_verify_null_passes_none_as_module_wide(self):
        """Overview with null top-level verify: passes None as module_wide_verify_cmd."""
        # The default fixture already has verify: null in the overview (via _make_fixture)
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8"
        )

        with unittest.mock.patch.object(
            millpy_implement, "finalize_from_output",
            return_value=0,
        ) as mock_finalize:
            rc, out = self._run_main([
                "test-batch",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        mock_finalize.assert_called_once()
        call_kwargs = mock_finalize.call_args.kwargs
        # A null overview verify must produce None (not the string "null")
        self.assertIsNone(call_kwargs.get("module_wide_verify_cmd"))


class TestClassifyStuckType(unittest.TestCase):

    def test_classify_command_not_found(self):
        """'command not found' in reason -> stuck_type=verify."""
        stuck_type = millpy_implement.classify_stuck_type("command not found: go")
        self.assertEqual(stuck_type, "verify")

    def test_classify_no_such_file(self):
        """'no such file' in reason -> stuck_type=verify."""
        stuck_type = millpy_implement.classify_stuck_type("No such file or directory")
        self.assertEqual(stuck_type, "verify")

    def test_classify_not_found(self):
        """'not found' in reason -> stuck_type=verify."""
        stuck_type = millpy_implement.classify_stuck_type("Binary not found")
        self.assertEqual(stuck_type, "verify")

    def test_classify_cannot_find(self):
        """'cannot find' in reason -> stuck_type=verify."""
        stuck_type = millpy_implement.classify_stuck_type("cannot find the specified file")
        self.assertEqual(stuck_type, "verify")

    def test_classify_errno_2(self):
        """'[errno 2]' in reason -> stuck_type=verify."""
        stuck_type = millpy_implement.classify_stuck_type("[Errno 2] No such file")
        self.assertEqual(stuck_type, "verify")

    def test_classify_winerror_2(self):
        """'winerror 2' in reason -> stuck_type=verify."""
        stuck_type = millpy_implement.classify_stuck_type("WinError 2: The system cannot find")
        self.assertEqual(stuck_type, "verify")

    def test_classify_cannot_run_program(self):
        """'cannot run program' in reason -> stuck_type=verify."""
        stuck_type = millpy_implement.classify_stuck_type("cannot run program go")
        self.assertEqual(stuck_type, "verify")

    def test_classify_timeout(self):
        """'timeout' in reason -> stuck_type=transient."""
        stuck_type = millpy_implement.classify_stuck_type("Claude CLI timed out after 1800s")
        self.assertEqual(stuck_type, "transient")

    def test_classify_dead_session(self):
        """'dead session' in reason -> stuck_type=transient."""
        stuck_type = millpy_implement.classify_stuck_type("claude --resume abc exited 1: dead session")
        self.assertEqual(stuck_type, "transient")

    def test_classify_rate_limit(self):
        """'rate limit' in reason -> stuck_type=transient."""
        stuck_type = millpy_implement.classify_stuck_type("claude rate-limited (exit 429)")
        self.assertEqual(stuck_type, "transient")

    def test_classify_generic_error(self):
        """Generic error with no known signal -> stuck_type=transient."""
        stuck_type = millpy_implement.classify_stuck_type("claude exited 1: unknown error")
        self.assertEqual(stuck_type, "transient")


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
