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
import _implementer_common  # noqa: E402

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
        def _subprocess_routing(argv, *a, **kw):
            # `git rev-list --count` must yield a parseable int (commits_made
            # counting added in main's reliability fix); other git calls return
            # a SHA-like stub as before.
            if len(argv) > 1 and argv[1] == "rev-list":
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout="0\n", stderr=""
                )
            return subprocess.CompletedProcess(
                args=argv, returncode=0, stdout="abc1234\n", stderr=""
            )

        self.mock_subprocess_run = _p(
            millpy_fix._subprocess_util, "run",
            side_effect=_subprocess_routing,
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
        self.mock_compute_scope_violations = _p(
            _implementer_common._cleanliness, "compute_scope_violations",
            return_value=[],
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
        call_count = [0]  # Use list to allow mutation in nested function

        def mock_subprocess_run(argv, **kwargs):
            # Track git rev-parse calls to return different values (start_sha vs final HEAD)
            if argv[0:2] == ["git", "rev-parse"]:
                call_count[0] += 1
                # First call (start_sha): return "abc1234"
                # Second call (final HEAD check): return "def5678" to simulate a commit was made
                if call_count[0] == 1:
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="abc1234\n", stderr=""
                    )
                else:
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="def5678\n", stderr=""
                    )
            # All other calls use the standard mock
            return self.mock_subprocess_run.return_value

        def mock_run(prompt_text, *, model, effort, session_id, resume, cwd, timeout):
            captured["prompt_text"] = prompt_text
            captured["resume"] = resume
            return ('{"status":"success","commit_sha":"abc","session_id":"fake"}\n', "fake-session")

        with unittest.mock.patch.object(
            millpy_fix._subprocess_util, "run",
            side_effect=mock_subprocess_run,
        ):
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
        call_count = [0]  # Use list to allow mutation in nested function

        def mock_subprocess_run(argv, **kwargs):
            # Track git rev-parse calls to return different values (start_sha vs final HEAD)
            if argv[0:2] == ["git", "rev-parse"]:
                call_count[0] += 1
                # First call (start_sha): return "abc1234"
                # Second call (final HEAD check): return "def5678" to simulate a commit was made
                if call_count[0] == 1:
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="abc1234\n", stderr=""
                    )
                else:
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="def5678\n", stderr=""
                    )
            # All other calls use the standard mock
            return self.mock_subprocess_run.return_value

        def mock_run(prompt_text, *, model, effort, session_id, resume, cwd, timeout):
            captured["prompt_text"] = prompt_text
            captured["resume"] = resume
            return ('{"status":"success","commit_sha":"abc","session_id":"fake"}\n', "fake-session")

        with unittest.mock.patch.object(
            millpy_fix._subprocess_util, "run",
            side_effect=mock_subprocess_run,
        ):
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

    def test_is_windows_lock_error_helper(self):
        """Unit test for _is_windows_lock_error helper with various inputs.

        Tests both the structured __cause__ winerror=32 check and the textual
        match for Windows file-locking signatures (distinct from cleanup-race signatures).
        """
        # Test message patterns that match lock-error signatures (not cleanup-race)
        self.assertTrue(
            millpy_fix._is_windows_lock_error(millpy_fix._llm_claude.LLMError("failed: WinError 32: file in use"))
        )
        self.assertTrue(
            millpy_fix._is_windows_lock_error(millpy_fix._llm_claude.LLMError("winerror 32"))
        )
        self.assertTrue(
            millpy_fix._is_windows_lock_error(millpy_fix._llm_claude.LLMError("process cannot access the file"))
        )
        self.assertTrue(
            millpy_fix._is_windows_lock_error(millpy_fix._llm_claude.LLMError("being used by another process"))
        )

        # Test cleanup-race signature (unlinkat) does NOT match lock-error helper
        self.assertFalse(
            millpy_fix._is_windows_lock_error(millpy_fix._llm_claude.LLMError("error: unlinkat ... Access is denied"))
        )

        # Test non-matching message (no lock-error signature, no winerror 32)
        self.assertFalse(
            millpy_fix._is_windows_lock_error(millpy_fix._llm_claude.LLMError("timeout after 60s"))
        )

        # Test OSError __cause__ with winerror=32 (structured check, takes precedence)
        e_with_cause_32 = millpy_fix._llm_claude.LLMError("file error")
        cause_32 = OSError("Cannot access file")
        cause_32.winerror = 32
        e_with_cause_32.__cause__ = cause_32
        self.assertTrue(millpy_fix._is_windows_lock_error(e_with_cause_32))

        # Test OSError __cause__ with winerror != 32 (access denied, winerror 5)
        # Exception message is "file error" which has no lock-error signature text
        e_with_cause_5 = millpy_fix._llm_claude.LLMError("file error")
        cause_5 = OSError("Access denied")
        cause_5.winerror = 5
        e_with_cause_5.__cause__ = cause_5
        # "file error" has no lock-error signature, so returns False
        self.assertFalse(millpy_fix._is_windows_lock_error(e_with_cause_5))

    def test_windows_lock_error_routes_to_verify(self):
        """Windows lock error from fixer -> stuck/verify JSON on stdout."""
        with unittest.mock.patch.object(
            millpy_fix._implementer_claude, "run",
            side_effect=millpy_fix._llm_claude.LLMError("WinError 32: file in use"),
        ):
            rc, out = self._run_main([
                "--scope", "batch",
                "--batch-name", "test-batch",
                "--review-file", str(self.review_file),
            ])

        self.assertEqual(rc, 1)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "verify")
        self.assertEqual(data["reason"], "WinError 32: file in use")

    def test_generic_llm_error_still_routes_to_transient(self):
        """Generic LLMError (non-Windows-lock) -> stuck/transient JSON (regression test)."""
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

            # Test holistic scope in same patch context
            rc, _ = self._run_main([
                "--scope", "holistic",
                "--review-file", str(self.review_file),
            ])
            self.assertEqual(rc, 0)

            # Verify both passed resume=False
            self.assertEqual(resume_values, [False, False])

    def test_start_sha_captured_and_passed_to_forward_output(self):
        """start_sha is captured from git rev-parse HEAD and passed to _forward_output."""
        known_sha = "deadbeef1234567890abcdef1234567890abcdef"
        captured_kwargs = {}

        def mock_forward_output(output, project_root, **kwargs):
            captured_kwargs.update(kwargs)
            return 0

        def mock_run(argv, **kwargs):
            if argv[0:2] == ["git", "rev-parse"]:
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout=f"{known_sha}\n", stderr=""
                )
            return self.mock_subprocess_run.return_value

        with unittest.mock.patch.object(millpy_fix, "_forward_output", side_effect=mock_forward_output):
            with unittest.mock.patch.object(
                millpy_fix._subprocess_util, "run",
                side_effect=mock_run,
            ):
                with unittest.mock.patch.object(
                    millpy_fix._implementer_claude, "run",
                    return_value=('{"status":"success","commit_sha":"abc","session_id":"fake"}\n', "fake"),
                ):
                    rc, _ = self._run_main([
                        "--scope", "batch",
                        "--batch-name", "test-batch",
                        "--review-file", str(self.review_file),
                    ])

        self.assertEqual(rc, 0)
        self.assertIn("start_sha", captured_kwargs, "start_sha must be passed to _forward_output")
        self.assertEqual(captured_kwargs["start_sha"], known_sha, f"expected start_sha={known_sha}, got {captured_kwargs.get('start_sha')}")

    def test_stage_prepare_batch_scope(self):
        """--stage prepare batch scope: renders brief, calls emit_prepare, no LLM call."""
        with unittest.mock.patch.object(millpy_fix._render, "render", return_value="Brief text"):
            with unittest.mock.patch.object(
                millpy_fix._implementer_claude, "run"
            ) as mock_run:
                rc, out = self._run_main([
                    "--scope", "batch",
                    "--batch-name", "test-batch",
                    "--review-file", str(self.review_file),
                    "--stage", "prepare",
                ])

        self.assertEqual(rc, 0)
        # LLM should not be called in prepare stage
        mock_run.assert_not_called()
        # Output should be prepare JSON envelope
        data = json.loads(out.strip())
        self.assertEqual(data["stage"], "prepare")
        self.assertEqual(data["role"], "fix")
        self.assertEqual(data["scope"], "test-batch")

    def test_stage_prepare_holistic_scope(self):
        """--stage prepare holistic scope: renders brief, calls emit_prepare, no LLM call."""
        with unittest.mock.patch.object(millpy_fix._render, "render", return_value="Brief text"):
            with unittest.mock.patch.object(
                millpy_fix._implementer_claude, "run"
            ) as mock_run:
                rc, out = self._run_main([
                    "--scope", "holistic",
                    "--review-file", str(self.review_file),
                    "--stage", "prepare",
                ])

        self.assertEqual(rc, 0)
        # LLM should not be called in prepare stage
        mock_run.assert_not_called()
        # Output should be prepare JSON envelope with holistic scope
        data = json.loads(out.strip())
        self.assertEqual(data["stage"], "prepare")
        self.assertEqual(data["scope"], "holistic")

    def test_stage_finalize_reads_agent_output(self):
        """--stage finalize: reads agent output file, calls finalize_from_output."""
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8"
        )

        with unittest.mock.patch.object(
            millpy_fix._implementer_claude, "run"
        ) as mock_run:
            rc, out = self._run_main([
                "--scope", "batch",
                "--batch-name", "test-batch",
                "--review-file", str(self.review_file),
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        # LLM should not be called in finalize stage
        mock_run.assert_not_called()
        # Output should be the agent output processed by _forward_output
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "success")


class TestMillpyFixBriefSizeGuard(unittest.TestCase):

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
        def _subprocess_routing(argv, *a, **kw):
            # `git rev-list --count` must yield a parseable int (commits_made
            # counting added in main's reliability fix); other git calls return
            # a SHA-like stub as before.
            if len(argv) > 1 and argv[1] == "rev-list":
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout="0\n", stderr=""
                )
            return subprocess.CompletedProcess(
                args=argv, returncode=0, stdout="abc1234\n", stderr=""
            )

        self.mock_subprocess_run = _p(
            millpy_fix._subprocess_util, "run",
            side_effect=_subprocess_routing,
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
        self.mock_compute_scope_violations = _p(
            _implementer_common._cleanliness, "compute_scope_violations",
            return_value=[],
        )

    def _run_main(self, argv):
        """Run main(argv) with stdout captured. Returns (rc, captured_stdout)."""
        buf = io.StringIO()
        with unittest.mock.patch("sys.stdout", buf):
            rc = millpy_fix.main(argv)
        return rc, buf.getvalue()

    def test_1_brief_size_guard_fires(self):
        """Brief exceeds max_implementer_prompt_chars -> stuck/transient, no LLM call."""
        self.mock_load_config.return_value = {
            "paths": {"status_md": "_mill/status.md"},
            "roles": {
                "implementer": {"self_fix_rounds": 2, "model": "sonnethigh"},
                "fixer": {"self_fix_rounds": 2, "model": "haiku"},
            },
            "llm": {"implementer_timeout": 1800, "max_implementer_prompt_chars": 10},
        }
        with unittest.mock.patch.object(millpy_fix._render, "render", return_value="x" * 20):
            with unittest.mock.patch.object(millpy_fix._implementer_claude, "run") as mock_run:
                rc, out = self._run_main(["--scope", "batch", "--batch-name", "test-batch", "--round", "1", "--review-file", str(self.review_file)])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "transient")
        self.assertIn("max_implementer_prompt_chars", data["reason"])
        mock_run.assert_not_called()

    def test_2_brief_size_guard_disabled(self):
        """max_implementer_prompt_chars = 0 (disabled) -> guard does not fire."""
        self.mock_load_config.return_value = {
            "paths": {"status_md": "_mill/status.md"},
            "roles": {
                "implementer": {"self_fix_rounds": 2, "model": "sonnethigh"},
                "fixer": {"self_fix_rounds": 2, "model": "haiku"},
            },
            "llm": {"implementer_timeout": 1800, "max_implementer_prompt_chars": 0},
        }
        with unittest.mock.patch.object(millpy_fix._render, "render", return_value="x" * 20):
            with unittest.mock.patch.object(
                millpy_fix._implementer_claude, "run",
                return_value=(
                    '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                    "fake-session",
                ),
            ) as mock_run:
                rc, out = self._run_main(["--scope", "batch", "--batch-name", "test-batch", "--round", "1", "--review-file", str(self.review_file)])

        self.assertEqual(rc, 0)
        # Verify that _implementer_claude.run was called (the guard did not fire)
        mock_run.assert_called_once()

    def test_nits_only_flag_appends_marker_and_flag(self):
        """
        Test that --nits-only flag causes nits_applied: true to be added to the envelope
        and a nits-fixed-<scope> marker to be appended to the status timeline.
        """
        status_path = self.tmp_path / "_mill" / "status.md"

        captured = {}
        call_count = [0]

        def mock_subprocess_run(argv, **kwargs):
            if argv[0:2] == ["git", "rev-parse"]:
                call_count[0] += 1
                if call_count[0] == 1:
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="abc1234\n", stderr=""
                    )
                else:
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="def5678\n", stderr=""
                    )
            return subprocess.CompletedProcess(
                args=argv, returncode=0, stdout="abc1234\n", stderr=""
            )

        def mock_run(prompt_text, *, model, effort, session_id, resume, cwd, timeout):
            captured["prompt_text"] = prompt_text
            captured["resume"] = resume
            return ('{"status":"success","commit_sha":"abc","session_id":"fake"}\n', "fake-session")

        with unittest.mock.patch.object(
            millpy_fix._subprocess_util, "run",
            side_effect=mock_subprocess_run,
        ):
            with unittest.mock.patch.object(
                millpy_fix._implementer_claude, "run",
                side_effect=mock_run,
            ):
                rc, out = self._run_main([
                    "--scope", "batch",
                    "--batch-name", "test-batch",
                    "--review-file", str(self.review_file),
                    "--round", "1",
                    "--nits-only",
                ])

        self.assertEqual(rc, 0)
        # Parse the output JSON
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "success")
        # Check that nits_applied flag was added
        self.assertTrue(data.get("nits_applied"), "nits_applied flag must be True when --nits-only is used")

        # Check that nits-fixed-test-batch marker was appended to timeline
        full = millpy_fix._status.read_full(status_path)
        self.assertTrue(
            any(e.startswith("nits-fixed-test-batch") for e in full["timeline"]),
            f"Expected nits-fixed-test-batch in timeline, got: {full['timeline']}",
        )

    def test_holistic_derived_verify_cmd_two_batches_failing(self):
        """Holistic with two batch verify commands, combined exits non-zero -> stuck/verify."""
        # Create plan with two batches, each with a verify command
        plan_dir = self.tmp_path / "_mill" / "plan"
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
            "  - name: batch1\n"
            "    file: 01-batch1.md\n"
            "    depends-on: []\n"
            "    verify: 'exit 1'\n"
            "  - name: batch2\n"
            "    file: 02-batch2.md\n"
            "    depends-on: [1]\n"
            "    verify: 'exit 0'\n"
            "```\n"
        )
        (plan_dir / "00-overview.md").write_text(overview_text, encoding="utf-8")
        (plan_dir / "01-batch1.md").write_text("# Batch: batch1\n\n```yaml\nverify: exit 1\n```\n", encoding="utf-8")
        (plan_dir / "02-batch2.md").write_text("# Batch: batch2\n\n```yaml\nverify: exit 0\n```\n", encoding="utf-8")

        captured = {}
        rev_parse_calls = [0]

        def mock_run(prompt_text, *, model, effort, session_id, resume, cwd, timeout):
            captured["prompt_text"] = prompt_text
            # Initialize git repo in the temp directory if not already done
            git_dir = self.tmp_path / ".git"
            if not git_dir.exists():
                subprocess.run(
                    ["git", "-C", str(self.tmp_path), "init"],
                    check=True, capture_output=True,
                )
                subprocess.run(
                    ["git", "-C", str(self.tmp_path), "config", "user.email", "test@test.com"],
                    check=True, capture_output=True,
                )
                subprocess.run(
                    ["git", "-C", str(self.tmp_path), "config", "user.name", "Test"],
                    check=True, capture_output=True,
                )
                # Create an initial commit
                (self.tmp_path / "README.md").write_text("initial", encoding="utf-8")
                subprocess.run(
                    ["git", "-C", str(self.tmp_path), "add", "README.md"],
                    check=True, capture_output=True,
                )
                subprocess.run(
                    ["git", "-C", str(self.tmp_path), "commit", "-m", "initial"],
                    check=True, capture_output=True,
                )
            # Make a commit so HEAD != start_sha
            subprocess.run(
                ["git", "-C", str(self.tmp_path), "commit", "--allow-empty", "-m", "fixer commit"],
                check=True, capture_output=True,
            )
            return ('{"status":"success","commit_sha":"abc","session_id":"fake"}\n', "fake-session")

        # Use the real subprocess.run for the verify gate so it actually executes the commands
        def mock_subprocess_run_with_verify(argv, **kwargs):
            # All git commands return mocked results
            if argv[0] == "git":
                if argv[1:3] == ["rev-parse", "HEAD"]:
                    rev_parse_calls[0] += 1
                    if rev_parse_calls[0] == 1:
                        # First call: start_sha
                        return subprocess.CompletedProcess(
                            args=argv, returncode=0, stdout="abc1234567890abcdef1234567890abcdef123456\n", stderr=""
                        )
                    else:
                        # Subsequent calls: final HEAD (after mock_run makes a commit)
                        result = subprocess.run(argv, capture_output=True, text=True, **kwargs)
                        return result
                elif argv[1:4] == ["config", "--global", "--get"]:
                    # Mock git config calls
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="Test User\n", stderr=""
                    )
                else:
                    # Other git commands
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="", stderr=""
                    )
            # For all other subprocess calls, including verify commands, use real subprocess
            # This allows the real _run_verify_gate to execute shell commands properly
            # Make sure to capture output
            return subprocess.run(argv, capture_output=True, text=True, **kwargs)

        with unittest.mock.patch.object(
            millpy_fix._subprocess_util, "run",
            side_effect=mock_subprocess_run_with_verify,
        ):
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
        self.assertEqual(data["status"], "stuck", f"expected stuck status, got {data}")
        self.assertEqual(data["stuck_type"], "verify", f"expected verify stuck_type, got {data}")

    def test_holistic_derived_verify_cmd_two_batches_passing(self):
        """Holistic with two batch verify commands, combined exits 0 -> success preserved."""
        # Create plan with two batches, each with a verify command
        plan_dir = self.tmp_path / "_mill" / "plan"
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
            "  - name: batch1\n"
            "    file: 01-batch1.md\n"
            "    depends-on: []\n"
            "    verify: 'exit 0'\n"
            "  - name: batch2\n"
            "    file: 02-batch2.md\n"
            "    depends-on: [1]\n"
            "    verify: 'exit 0'\n"
            "```\n"
        )
        (plan_dir / "00-overview.md").write_text(overview_text, encoding="utf-8")
        (plan_dir / "01-batch1.md").write_text("# Batch: batch1\n\n```yaml\nverify: exit 0\n```\n", encoding="utf-8")
        (plan_dir / "02-batch2.md").write_text("# Batch: batch2\n\n```yaml\nverify: exit 0\n```\n", encoding="utf-8")

        captured = {}
        rev_parse_calls = [0]

        def mock_run(prompt_text, *, model, effort, session_id, resume, cwd, timeout):
            captured["prompt_text"] = prompt_text
            # Initialize git repo in the temp directory if not already done
            git_dir = self.tmp_path / ".git"
            if not git_dir.exists():
                subprocess.run(
                    ["git", "-C", str(self.tmp_path), "init"],
                    check=True, capture_output=True,
                )
                subprocess.run(
                    ["git", "-C", str(self.tmp_path), "config", "user.email", "test@test.com"],
                    check=True, capture_output=True,
                )
                subprocess.run(
                    ["git", "-C", str(self.tmp_path), "config", "user.name", "Test"],
                    check=True, capture_output=True,
                )
                # Create an initial commit
                (self.tmp_path / "README.md").write_text("initial", encoding="utf-8")
                subprocess.run(
                    ["git", "-C", str(self.tmp_path), "add", "README.md"],
                    check=True, capture_output=True,
                )
                subprocess.run(
                    ["git", "-C", str(self.tmp_path), "commit", "-m", "initial"],
                    check=True, capture_output=True,
                )
            # Make a commit so HEAD != start_sha
            subprocess.run(
                ["git", "-C", str(self.tmp_path), "commit", "--allow-empty", "-m", "fixer commit"],
                check=True, capture_output=True,
            )
            return ('{"status":"success","commit_sha":"abc","session_id":"fake"}\n', "fake-session")

        # Use the real subprocess.run for the verify gate so it actually executes the commands
        def mock_subprocess_run_with_verify(argv, **kwargs):
            # All git commands return mocked results
            if argv[0] == "git":
                if argv[1:3] == ["rev-parse", "HEAD"]:
                    rev_parse_calls[0] += 1
                    if rev_parse_calls[0] == 1:
                        # First call: start_sha
                        return subprocess.CompletedProcess(
                            args=argv, returncode=0, stdout="abc1234567890abcdef1234567890abcdef123456\n", stderr=""
                        )
                    else:
                        # Subsequent calls: final HEAD (after mock_run makes a commit)
                        result = subprocess.run(argv, capture_output=True, text=True, **kwargs)
                        return result
                elif argv[1:4] == ["config", "--global", "--get"]:
                    # Mock git config calls
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="Test User\n", stderr=""
                    )
                else:
                    # Other git commands
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="", stderr=""
                    )
            # For all other subprocess calls, including verify commands, use real subprocess
            # This allows the real _run_verify_gate to execute shell commands properly
            # Make sure to capture output
            return subprocess.run(argv, capture_output=True, text=True, **kwargs)

        with unittest.mock.patch.object(
            millpy_fix._subprocess_util, "run",
            side_effect=mock_subprocess_run_with_verify,
        ):
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
        self.assertEqual(data["status"], "success", f"expected success status, got {data}")

    def test_holistic_all_null_verifies(self):
        """Holistic with all verify: null -> no gate, success preserved."""
        # Create plan with two batches, both with null verify
        plan_dir = self.tmp_path / "_mill" / "plan"
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
            "  - name: batch1\n"
            "    file: 01-batch1.md\n"
            "    depends-on: []\n"
            "    verify: null\n"
            "  - name: batch2\n"
            "    file: 02-batch2.md\n"
            "    depends-on: [1]\n"
            "    verify: null\n"
            "```\n"
        )
        (plan_dir / "00-overview.md").write_text(overview_text, encoding="utf-8")
        (plan_dir / "01-batch1.md").write_text("# Batch: batch1\n", encoding="utf-8")
        (plan_dir / "02-batch2.md").write_text("# Batch: batch2\n", encoding="utf-8")

        captured = {}
        rev_parse_calls = [0]

        def mock_run(prompt_text, *, model, effort, session_id, resume, cwd, timeout):
            captured["prompt_text"] = prompt_text
            # Initialize git repo in the temp directory if not already done
            git_dir = self.tmp_path / ".git"
            if not git_dir.exists():
                subprocess.run(
                    ["git", "-C", str(self.tmp_path), "init"],
                    check=True, capture_output=True,
                )
                subprocess.run(
                    ["git", "-C", str(self.tmp_path), "config", "user.email", "test@test.com"],
                    check=True, capture_output=True,
                )
                subprocess.run(
                    ["git", "-C", str(self.tmp_path), "config", "user.name", "Test"],
                    check=True, capture_output=True,
                )
                # Create an initial commit
                (self.tmp_path / "README.md").write_text("initial", encoding="utf-8")
                subprocess.run(
                    ["git", "-C", str(self.tmp_path), "add", "README.md"],
                    check=True, capture_output=True,
                )
                subprocess.run(
                    ["git", "-C", str(self.tmp_path), "commit", "-m", "initial"],
                    check=True, capture_output=True,
                )
            # Make a commit so HEAD != start_sha
            subprocess.run(
                ["git", "-C", str(self.tmp_path), "commit", "--allow-empty", "-m", "fixer commit"],
                check=True, capture_output=True,
            )
            return ('{"status":"success","commit_sha":"abc","session_id":"fake"}\n', "fake-session")

        # Use the real subprocess.run for the verify gate so it actually executes the commands
        def mock_subprocess_run_with_verify(argv, **kwargs):
            # All git commands return mocked results
            if argv[0] == "git":
                if argv[1:3] == ["rev-parse", "HEAD"]:
                    rev_parse_calls[0] += 1
                    if rev_parse_calls[0] == 1:
                        # First call: start_sha
                        return subprocess.CompletedProcess(
                            args=argv, returncode=0, stdout="abc1234567890abcdef1234567890abcdef123456\n", stderr=""
                        )
                    else:
                        # Subsequent calls: final HEAD (after mock_run makes a commit)
                        result = subprocess.run(argv, capture_output=True, text=True, **kwargs)
                        return result
                elif argv[1:4] == ["config", "--global", "--get"]:
                    # Mock git config calls
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="Test User\n", stderr=""
                    )
                else:
                    # Other git commands
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="", stderr=""
                    )
            # For all other subprocess calls, including verify commands, use real subprocess
            # This allows the real _run_verify_gate to execute shell commands properly
            # Make sure to capture output
            return subprocess.run(argv, capture_output=True, text=True, **kwargs)

        with unittest.mock.patch.object(
            millpy_fix._subprocess_util, "run",
            side_effect=mock_subprocess_run_with_verify,
        ):
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
        self.assertEqual(data["status"], "success", f"expected success status, got {data}")

    def test_brief_contains_unsatisfiable_demand_instruction(self):
        """Assert fixer briefs contain unsatisfiable-demand instruction."""
        # Read the brief templates
        batch_brief_path = Path(__file__).resolve().parent.parent / "templates" / "fixer-batch-brief.md"
        holistic_brief_path = Path(__file__).resolve().parent.parent / "templates" / "fixer-holistic-brief.md"

        batch_brief = batch_brief_path.read_text(encoding="utf-8")
        holistic_brief = holistic_brief_path.read_text(encoding="utf-8")

        # Check batch brief contains unsatisfiable-demand instruction
        self.assertIn("unsatisfiable", batch_brief.lower(), "fixer-batch-brief.md must contain unsatisfiable-demand instruction")
        self.assertIn("stuck_type: logic", batch_brief, "fixer-batch-brief.md must mention stuck_type: logic")
        self.assertIn("cannot pass", batch_brief.lower(), "fixer-batch-brief.md must reference cannot pass")

        # Check holistic brief contains unsatisfiable-demand instruction
        self.assertIn("unsatisfiable", holistic_brief.lower(), "fixer-holistic-brief.md must contain unsatisfiable-demand instruction")
        self.assertIn("stuck_type: logic", holistic_brief, "fixer-holistic-brief.md must mention stuck_type: logic")
        self.assertIn("cannot pass", holistic_brief.lower(), "fixer-holistic-brief.md must reference cannot pass")


if __name__ == "__main__":
    unittest.main()
