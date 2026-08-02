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
        self.mock_resolve_container_path = _p(
            millpy_fix._paths, "resolve_container_path",
            return_value=self.tmp_path.parent,
        )
        self.mock_resolve_active_hub = _p(
            millpy_fix._paths, "resolve_active_hub",
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
                args=argv, returncode=0, stdout="abc1234000000000000000000000000000000000\n", stderr=""
            )

        self.mock_subprocess_run = _p(
            millpy_fix._subprocess_util, "run",
            side_effect=_subprocess_routing,
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="abc1234000000000000000000000000000000000\n", stderr=""
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
                # First call (start_sha): return the abc1234... full SHA
                # Second call (final HEAD check): return the def5678... full SHA to simulate a commit was made
                if call_count[0] == 1:
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="abc1234000000000000000000000000000000000\n", stderr=""
                    )
                else:
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="def5678000000000000000000000000000000000\n", stderr=""
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

    def test_load_config_uses_hub_root_when_hub_in_subdirectory(self):
        """#728 repro: hub lives in a subdirectory of the outer git repo.

        Both the initial load_config call (arg1 = project_root, from
        resolve_hub_path()) and the post-resolve_active_hub reload must be
        invoked with the resolved hub root, never the outer git-repo root --
        otherwise the hub's own mill-config.yaml is silently missed in favor
        of a template/primary-clone fallback found by walking from git_root.
        """
        hub_dir = self.tmp_path / "sub" / "hub"
        hub_dir.mkdir(parents=True, exist_ok=True)
        review_file = _make_fixture(hub_dir)
        # resolve_hub_path (bootstrap project_root) and resolve_active_hub
        # (corrected project_root) both point at the subdirectory hub.
        # resolve_git_root keeps returning self.tmp_path (the outer root),
        # which must never be passed as load_config's hub_root argument.
        self.mock_resolve_hub_path = unittest.mock.patch.object(
            millpy_fix._paths, "resolve_hub_path", return_value=hub_dir
        )
        self.mock_resolve_hub_path.start()
        self.addCleanup(self.mock_resolve_hub_path.stop)
        self.mock_resolve_active_hub.return_value = hub_dir

        observed_cfgs = []

        def _fake_load_config(hub_root, mill_dir):
            if hub_root == hub_dir:
                cfg = {
                    "paths": {"status_md": "_mill/status.md"},
                    "spawn": {"branch_prefix": "hub-own-prefix"},
                    "roles": {
                        "implementer": {"self_fix_rounds": 2, "model": "sonnethigh"},
                        "fixer": {"model": "haiku"},
                    },
                    "llm": {"implementer_timeout": 1800},
                }
            else:
                # Stand-in for the template/primary-clone fallback the pre-fix
                # code would silently pick up when passed the outer git-repo root.
                cfg = {
                    "spawn": {"branch_prefix": "template-fallback-prefix"},
                    "llm": {"implementer_timeout": 1800},
                }
            observed_cfgs.append((hub_root, cfg))
            return cfg

        self.mock_load_config.side_effect = _fake_load_config

        def mock_run(prompt_text, *, model, effort, session_id, resume, cwd, timeout):
            return ('{"status":"success","commit_sha":"abc","session_id":"fake"}\n', "fake-session")

        with unittest.mock.patch.object(
            millpy_fix._implementer_claude, "run", side_effect=mock_run,
        ):
            rc, out = self._run_main([
                "--scope", "batch",
                "--batch-name", "test-batch",
                "--review-file", str(review_file),
                "--round", "1",
            ])

        self.assertEqual(rc, 0)
        self.assertTrue(observed_cfgs)
        for hub_root_arg, cfg in observed_cfgs:
            self.assertEqual(hub_root_arg, hub_dir)
            self.assertEqual(cfg["spawn"]["branch_prefix"], "hub-own-prefix")

    def test_cfg_reload_after_resolve_active_hub_used_for_downstream_values(self):
        """Bootstrap cfg and the resolve_active_hub-corrected reload can genuinely
        differ. Downstream values that read cfg -- self_fix_rounds baked into the
        rendered brief, the fixer model name passed to _reviewers.resolve, and
        the fixer timeout passed to _implementer_claude.run -- must come from
        the reloaded config, not the stale bootstrap one.
        """
        corrected_root = self.tmp_path / "corrected-worktree"
        corrected_root.mkdir(parents=True, exist_ok=True)
        review_file = _make_fixture(corrected_root)
        self.mock_resolve_active_hub.return_value = corrected_root

        bootstrap_cfg = {
            "paths": {"status_md": "_mill/status.md"},
            "roles": {
                "implementer": {"self_fix_rounds": 2},
                "fixer": {"model": "bootstrap-model"},
            },
            "llm": {"implementer_timeout": 111},
        }
        reloaded_cfg = {
            "paths": {"status_md": "_mill/status.md"},
            "roles": {
                "implementer": {"self_fix_rounds": 9},
                "fixer": {"model": "reloaded-model"},
            },
            "llm": {"implementer_timeout": 999},
        }

        def _fake_load_config(hub_root, mill_dir):
            return reloaded_cfg if hub_root == corrected_root else bootstrap_cfg

        self.mock_load_config.side_effect = _fake_load_config

        captured = {}

        def mock_run(prompt_text, *, model, effort, session_id, resume, cwd, timeout):
            captured["prompt_text"] = prompt_text
            captured["timeout"] = timeout
            return ('{"status":"success","commit_sha":"abc","session_id":"fake"}\n', "fake-session")

        with unittest.mock.patch.object(
            millpy_fix._implementer_claude, "run", side_effect=mock_run,
        ):
            rc, out = self._run_main([
                "--scope", "batch",
                "--batch-name", "test-batch",
                "--review-file", str(review_file),
                "--round", "1",
            ])

        self.assertEqual(rc, 0)
        # self_fix_rounds baked into the brief must come from the reloaded
        # config (9), never the bootstrap config's value (2).
        self.assertIn("9", captured["prompt_text"])
        # fixer model_name passed to _reviewers.resolve must come from the
        # reloaded config too.
        self.mock_reviewers_resolve.assert_called_with(
            self.mock_reviewers_load.return_value, "reloaded-model"
        )
        # fixer timeout passed to _implementer_claude.run must come from the
        # reloaded config's llm.implementer_timeout (999), not the bootstrap
        # config's (111). fixer_spec has no "timeout" key here so the
        # cfg fallback is exercised.
        self.assertEqual(captured["timeout"], 999)

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
                # First call (start_sha): return the abc1234... full SHA
                # Second call (final HEAD check): return the def5678... full SHA to simulate a commit was made
                if call_count[0] == 1:
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="abc1234000000000000000000000000000000000\n", stderr=""
                    )
                else:
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="def5678000000000000000000000000000000000\n", stderr=""
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

    def test_project_root_rebind_uses_resolve_active_hub_not_original_hub_path(self):
        """project_root rebinds to resolve_active_hub's value, not the file's original (escaped) resolution.

        This file resolves project_root via a real, unmocked resolve_hub_path() call
        (setUp mocks only resolve_git_root -- see the per-file description in Card 12)
        that succeeds because cwd is chdir'd to self.tmp_path, which has its own
        .millhouse/config.local.yaml. Overriding resolve_active_hub to a decoy directory
        distinct from self.tmp_path simulates the "escaped to main worktree" scenario:
        the original resolution still points at self.tmp_path, but the corrected
        resolve_active_hub call (added by the rebind fix) returns the right place.
        briefs_dir (surfaced via --stage prepare's brief_path in the envelope) must
        resolve under the decoy, proving project_root was rebound.
        """
        corrected_root = self.tmp_path / "corrected-worktree"
        corrected_root.mkdir(parents=True, exist_ok=True)
        _make_fixture(corrected_root)
        self.mock_resolve_active_hub.return_value = corrected_root

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
        mock_run.assert_not_called()
        data = json.loads(out.strip())
        brief_path = Path(data["brief_path"])
        self.assertEqual(brief_path.parent, corrected_root / "_mill" / "briefs")
        self.assertFalse(brief_path.is_relative_to(self.tmp_path / "_mill" / "briefs"))

    def test_stage_prepare_batch_scope_with_nits_only(self):
        """--stage prepare --nits-only: prepare envelope carries nits_only:true (#619)."""
        with unittest.mock.patch.object(millpy_fix._render, "render", return_value="Brief text"):
            with unittest.mock.patch.object(
                millpy_fix._implementer_claude, "run"
            ) as mock_run:
                rc, out = self._run_main([
                    "--scope", "batch",
                    "--batch-name", "test-batch",
                    "--review-file", str(self.review_file),
                    "--stage", "prepare",
                    "--nits-only",
                ])

        self.assertEqual(rc, 0)
        # LLM should not be called in prepare stage
        mock_run.assert_not_called()
        # Output should be prepare JSON envelope with nits_only:true
        data = json.loads(out.strip())
        self.assertIs(data["nits_only"], True)

    def test_stage_prepare_batch_scope_without_nits_only_omits_field(self):
        """--stage prepare without --nits-only: prepare envelope omits nits_only entirely (#619)."""
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
        # Output should be prepare JSON envelope with no nits_only key at all
        data = json.loads(out.strip())
        self.assertNotIn("nits_only", data)

    def test_stage_prepare_batch_scope_includes_effort_from_fixer_spec(self):
        """--stage prepare envelope carries the resolved fixer spec's effort tier (#628, #633).

        Overrides the default haiku-spec mock (no effort field) with a sonnethigh-style
        spec that resolves effort:"high", mirroring the millpy-implement.py Card 5 test.
        """
        self.mock_reviewers_resolve.return_value = {
            "type": "single",
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "effort": "high",
        }
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
        # Output should be prepare JSON envelope with the resolved effort tier
        data = json.loads(out.strip())
        self.assertEqual(data["effort"], "high")

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

    def test_main_reports_clean_message_on_exhausted_wiki_startup_error(self):
        """slug_from_branch exhausting the cold-daemon retry -> clean stderr message, exit 1, no traceback."""
        self.mock_slug_from_branch.side_effect = millpy_fix.WikiStartupError(
            "daemon did not start within timeout"
        )

        stderr_buf = io.StringIO()
        with unittest.mock.patch("sys.stderr", stderr_buf):
            rc, out = self._run_main([
                "--scope", "batch",
                "--batch-name", "test-batch",
                "--review-file", str(self.review_file),
                "--round", "1",
            ])

        self.assertEqual(rc, 1)
        stderr_output = stderr_buf.getvalue()
        # A clean except clause must have caught this -- no raw unhandled traceback.
        self.assertNotIn("Traceback (most recent call last)", stderr_output)

    def test_fixer_tier_warning_fires_when_reviewer_stronger(self):
        """--stage prepare: reviewer configured stronger than fixer -> [fixer-tier] warning on stderr."""
        self.mock_load_config.return_value = {
            "paths": {"status_md": "_mill/status.md"},
            "roles": {
                "implementer": {"self_fix_rounds": 2, "model": "sonnethigh"},
                "fixer": {"model": "haiku"},
                "code-review": {"batch": {"reviewer": "opushigh"}},
            },
            "llm": {"implementer_timeout": 1800},
        }
        self.mock_reviewers_resolve.side_effect = lambda registry, name: (
            {"type": "single", "provider": "claude", "model": "claude-opus-4-7", "effort": "high"}
            if name == "opushigh"
            else {"type": "single", "provider": "claude", "model": "claude-haiku-4-5-20251001"}
        )

        stderr_buf = io.StringIO()
        with unittest.mock.patch.object(millpy_fix._render, "render", return_value="Brief text"):
            with unittest.mock.patch.object(millpy_fix._implementer_claude, "run") as mock_run:
                with unittest.mock.patch("sys.stderr", stderr_buf):
                    rc, out = self._run_main([
                        "--scope", "batch",
                        "--batch-name", "test-batch",
                        "--review-file", str(self.review_file),
                        "--stage", "prepare",
                    ])

        self.assertEqual(rc, 0)
        # LLM should not be called in prepare stage
        mock_run.assert_not_called()
        self.assertIn("[fixer-tier]", stderr_buf.getvalue())

    def test_fixer_tier_warning_silent_by_default(self):
        """--stage prepare, default fixture (no roles.code-review key, resolve mock unmodified) -> no [fixer-tier] warning."""
        stderr_buf = io.StringIO()
        with unittest.mock.patch.object(millpy_fix._render, "render", return_value="Brief text"):
            with unittest.mock.patch.object(millpy_fix._implementer_claude, "run") as mock_run:
                with unittest.mock.patch("sys.stderr", stderr_buf):
                    rc, out = self._run_main([
                        "--scope", "batch",
                        "--batch-name", "test-batch",
                        "--review-file", str(self.review_file),
                        "--stage", "prepare",
                    ])

        self.assertEqual(rc, 0)
        # LLM should not be called in prepare stage
        mock_run.assert_not_called()
        self.assertNotIn("[fixer-tier]", stderr_buf.getvalue())

    def test_holistic_finalize_status_path_filters_pending_batch_and_logs_skip(self):
        """Card 5: status_path is threaded into the holistic-finalize iter_batch_verifies
        call, dropping a pending batch's verify from the joined command and logging
        `[millpy-fix] skipped batch1: batch not approved` to stderr."""
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

        status_path = self.tmp_path / "_mill" / "status.md"
        millpy_fix._status.init_batches(status_path, ["batch1", "batch2"])
        millpy_fix._status.set_batch_field(status_path, "batch1", "state", "pending")
        millpy_fix._status.set_batch_field(status_path, "batch2", "state", "approved")

        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8",
        )

        captured_kwargs = {}

        def mock_finalize_from_output(agent_output_path_arg, project_root, **kwargs):
            captured_kwargs.update(kwargs)
            return 0

        stderr_buf = io.StringIO()
        with unittest.mock.patch.object(
            millpy_fix, "finalize_from_output", side_effect=mock_finalize_from_output
        ):
            with unittest.mock.patch("sys.stderr", stderr_buf):
                rc, _ = self._run_main([
                    "--scope", "holistic",
                    "--review-file", str(self.review_file),
                    "--stage", "finalize",
                    "--agent-output", str(agent_output_path),
                ])

        self.assertEqual(rc, 0)
        # Only batch2's ("approved") command survives -- batch1 ("pending") is filtered.
        # A single contributing batch is still wrapped in its own subshell.
        self.assertEqual(captured_kwargs.get("verify_cmd"), "(exit 0)")
        self.assertIn(
            "[millpy-fix] skipped batch1: batch not approved",
            stderr_buf.getvalue(),
        )

    def test_holistic_finalize_status_path_logs_target_removed_skip(self):
        """Card 5: an approved batch whose verify command references a path a later
        approved batch's Deletes: removes is filtered by iter_batch_verifies (reason
        2/3b), and this helper attributes it to 'target removed by later batch' --
        not 'batch not approved' -- since batch1 itself IS approved."""
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
            "    verify: 'go test tools/x/cmd/app'\n"
            "  - name: batch2\n"
            "    file: 02-batch2.md\n"
            "    depends-on: [1]\n"
            "    verify: null\n"
            "```\n"
        )
        (plan_dir / "00-overview.md").write_text(overview_text, encoding="utf-8")
        (plan_dir / "01-batch1.md").write_text(
            "# Batch: batch1\n\n```yaml\nverify: go test tools/x/cmd/app\n```\n",
            encoding="utf-8",
        )
        (plan_dir / "02-batch2.md").write_text(
            "# Batch: batch2\n\n```yaml\nverify: null\n```\n\n"
            "- **Deletes:** `tools/x/cmd/app`\n",
            encoding="utf-8",
        )

        status_path = self.tmp_path / "_mill" / "status.md"
        millpy_fix._status.init_batches(status_path, ["batch1", "batch2"])
        millpy_fix._status.set_batch_field(status_path, "batch1", "state", "approved")
        millpy_fix._status.set_batch_field(status_path, "batch2", "state", "approved")

        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8",
        )

        captured_kwargs = {}

        def mock_finalize_from_output(agent_output_path_arg, project_root, **kwargs):
            captured_kwargs.update(kwargs)
            return 0

        stderr_buf = io.StringIO()
        with unittest.mock.patch.object(
            millpy_fix, "finalize_from_output", side_effect=mock_finalize_from_output
        ):
            with unittest.mock.patch("sys.stderr", stderr_buf):
                rc, _ = self._run_main([
                    "--scope", "holistic",
                    "--review-file", str(self.review_file),
                    "--stage", "finalize",
                    "--agent-output", str(agent_output_path),
                ])

        self.assertEqual(rc, 0)
        # No verify command survives -- batch1's target was removed, batch2's own is null.
        self.assertIsNone(captured_kwargs.get("verify_cmd"))
        self.assertIn(
            "[millpy-fix] skipped batch1: target removed by later batch",
            stderr_buf.getvalue(),
        )

    def test_holistic_full_stage_status_path_filters_pending_batch_and_logs_skip(self):
        """Card 5: non-finalize holistic (--stage full) path also threads status_path into
        iter_batch_verifies, filtering out a pending batch and logging the skip to stderr."""
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

        status_path = self.tmp_path / "_mill" / "status.md"
        millpy_fix._status.init_batches(status_path, ["batch1", "batch2"])
        millpy_fix._status.set_batch_field(status_path, "batch1", "state", "pending")
        millpy_fix._status.set_batch_field(status_path, "batch2", "state", "approved")

        # Initialize git repo in the temp directory before running the test
        git_dir = self.tmp_path / ".git"
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

        captured = {}
        rev_parse_calls = [0]

        def mock_run(prompt_text, *, model, effort, session_id, resume, cwd, timeout):
            captured["prompt_text"] = prompt_text
            # Make a commit so HEAD != start_sha
            subprocess.run(
                ["git", "-C", str(self.tmp_path), "commit", "--allow-empty", "-m", "fixer commit"],
                check=True, capture_output=True,
            )
            return ('{"status":"success","commit_sha":"abc","session_id":"fake"}\n', "fake-session")

        def mock_subprocess_run(argv, **kwargs):
            # All git commands are handled specially
            if argv[0] == "git":
                if argv[1:3] == ["rev-parse", "HEAD"]:
                    rev_parse_calls[0] += 1
                    if rev_parse_calls[0] == 1:
                        # First call: start_sha - return a fixed SHA
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
                elif argv[1] == "push":
                    # Mock git push - always succeed
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="", stderr=""
                    )
                else:
                    # Other git commands (add, commit, etc) - use real subprocess
                    return subprocess.run(argv, capture_output=True, text=True, **kwargs)
            # For all other subprocess calls, use real subprocess
            return subprocess.run(argv, capture_output=True, text=True, **kwargs)

        stderr_buf = io.StringIO()
        with unittest.mock.patch.object(
            millpy_fix._subprocess_util, "run",
            side_effect=mock_subprocess_run,
        ):
            with unittest.mock.patch.object(
                millpy_fix._implementer_claude, "run",
                side_effect=mock_run,
            ):
                with unittest.mock.patch("sys.stderr", stderr_buf):
                    rc, out = self._run_main([
                        "--scope", "holistic",
                        "--review-file", str(self.review_file),
                        "--round", "1",
                    ])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "success")
        # Verify that batch1 (pending) was skipped with the correct reason
        self.assertIn(
            "[millpy-fix] skipped batch1: batch not approved",
            stderr_buf.getvalue(),
        )


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
        self.mock_resolve_container_path = _p(
            millpy_fix._paths, "resolve_container_path",
            return_value=self.tmp_path.parent,
        )
        self.mock_resolve_active_hub = _p(
            millpy_fix._paths, "resolve_active_hub",
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
                args=argv, returncode=0, stdout="abc1234000000000000000000000000000000000\n", stderr=""
            )

        self.mock_subprocess_run = _p(
            millpy_fix._subprocess_util, "run",
            side_effect=_subprocess_routing,
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="abc1234000000000000000000000000000000000\n", stderr=""
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
                        args=argv, returncode=0, stdout="abc1234000000000000000000000000000000000\n", stderr=""
                    )
                else:
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0, stdout="def5678000000000000000000000000000000000\n", stderr=""
                    )
            return subprocess.CompletedProcess(
                args=argv, returncode=0, stdout="abc1234000000000000000000000000000000000\n", stderr=""
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

    def test_nits_only_all_pushback_zero_commit_is_success_not_stuck(self):
        """
        #582 regression: a --nits-only pass that legitimately pushes back on every
        NIT finding makes zero content commits (HEAD never moves from start_sha).
        This must be reported as success with the nits-fixed marker written, not
        demoted to stuck/logic by the no-content-commit gate.
        """
        status_path = self.tmp_path / "_mill" / "status.md"

        # Every git rev-parse HEAD call returns the SAME sha -- HEAD never moves,
        # simulating the all-pushback, zero-commit case.
        def mock_subprocess_run(argv, **kwargs):
            if argv[0:2] == ["git", "rev-parse"]:
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout="abc1234000000000000000000000000000000000\n", stderr=""
                )
            return subprocess.CompletedProcess(
                args=argv, returncode=0, stdout="abc1234000000000000000000000000000000000\n", stderr=""
            )

        def mock_run(prompt_text, *, model, effort, session_id, resume, cwd, timeout):
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
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "success")
        self.assertIsNone(data.get("stuck_type"))
        self.assertTrue(
            data.get("nits_applied"),
            "nits_applied flag must be True on the zero-commit all-pushback success path",
        )

        # Check that nits-fixed-test-batch marker was still appended to timeline.
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

        # status_path now gates iter_batch_verifies on approval state -- both
        # batches must be "approved" for their verify commands to survive the
        # filter and reach the holistic join, matching the pre-status_path
        # unfiltered behavior this test exercises.
        status_path = self.tmp_path / "_mill" / "status.md"
        millpy_fix._status.init_batches(status_path, ["batch1", "batch2"])
        millpy_fix._status.set_batch_field(status_path, "batch1", "state", "approved")
        millpy_fix._status.set_batch_field(status_path, "batch2", "state", "approved")

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

        # status_path now gates iter_batch_verifies on approval state -- both
        # batches must be "approved" for their verify commands to survive the
        # filter and reach the holistic join, matching the pre-status_path
        # unfiltered behavior this test exercises.
        status_path = self.tmp_path / "_mill" / "status.md"
        millpy_fix._status.init_batches(status_path, ["batch1", "batch2"])
        millpy_fix._status.set_batch_field(status_path, "batch1", "state", "approved")
        millpy_fix._status.set_batch_field(status_path, "batch2", "state", "approved")

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

    def test_batch_scope_nested_layout_cwd_hub_threads_cwd_override(self):
        """Nested layout: batch verify: {cwd: hub, command: ...} resolves and threads cwd_override (Card 19)."""
        nested_hub = self.tmp_path / "hub"
        nested_hub.mkdir(parents=True, exist_ok=True)
        _make_fixture(nested_hub)

        batch_file = nested_hub / "_mill" / "plan" / "01-test-batch.md"
        batch_file.write_text(
            "```yaml\n"
            "verify:\n"
            "  cwd: hub\n"
            "  command: exit 0\n"
            "```\n\n"
            "# Batch: test-batch\n",
            encoding="utf-8",
        )

        captured_kwargs = {}

        def mock_forward_output(output, project_root, **kwargs):
            captured_kwargs.update(kwargs)
            return 0

        with (
            unittest.mock.patch.object(
                millpy_fix._paths, "resolve_hub_path", return_value=nested_hub
            ),
            # The rebind (Card 10) supersedes resolve_hub_path's value with
            # resolve_active_hub's for project_root -- override it here too so
            # this nested-hub simulation still resolves project_root to nested_hub.
            unittest.mock.patch.object(
                millpy_fix._paths, "resolve_active_hub", return_value=nested_hub
            ),
            unittest.mock.patch.object(
                millpy_fix, "_forward_output", side_effect=mock_forward_output
            ),
            unittest.mock.patch.object(
                millpy_fix._implementer_claude, "run",
                return_value=(
                    '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                    "fake",
                ),
            ),
        ):
            rc, out = self._run_main([
                "--scope", "batch",
                "--batch-name", "test-batch",
                "--review-file", str(self.review_file),
            ])

        self.assertEqual(rc, 0)
        self.assertEqual(captured_kwargs.get("verify_cmd"), "exit 0")
        self.assertEqual(captured_kwargs.get("cwd_override"), nested_hub)

    def test_holistic_scope_uniform_cwd_hub_threads_cwd_override(self):
        """Holistic scope: batches all resolving to cwd: hub join and thread cwd_override (Card 20)."""
        nested_hub = self.tmp_path / "hub"
        nested_hub.mkdir(parents=True, exist_ok=True)
        _make_fixture(nested_hub)

        plan_dir = nested_hub / "_mill" / "plan"
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
        (plan_dir / "01-batch1.md").write_text(
            "```yaml\nverify:\n  cwd: hub\n  command: exit 0\n```\n\n# Batch: batch1\n",
            encoding="utf-8",
        )
        (plan_dir / "02-batch2.md").write_text(
            "```yaml\nverify:\n  cwd: hub\n  command: exit 0\n```\n\n# Batch: batch2\n",
            encoding="utf-8",
        )

        # status_path now gates iter_batch_verifies on approval state -- both
        # batches must be "approved" for their verify commands to survive the
        # filter and reach the holistic join, matching the pre-status_path
        # unfiltered behavior this test exercises.
        nested_status_path = nested_hub / "_mill" / "status.md"
        millpy_fix._status.init_batches(nested_status_path, ["batch1", "batch2"])
        millpy_fix._status.set_batch_field(nested_status_path, "batch1", "state", "approved")
        millpy_fix._status.set_batch_field(nested_status_path, "batch2", "state", "approved")

        captured_kwargs = {}

        def mock_forward_output(output, project_root, **kwargs):
            captured_kwargs.update(kwargs)
            return 0

        with (
            unittest.mock.patch.object(
                millpy_fix._paths, "resolve_hub_path", return_value=nested_hub
            ),
            # The rebind (Card 10) supersedes resolve_hub_path's value with
            # resolve_active_hub's for project_root -- override it here too so
            # this nested-hub simulation still resolves project_root to nested_hub.
            unittest.mock.patch.object(
                millpy_fix._paths, "resolve_active_hub", return_value=nested_hub
            ),
            unittest.mock.patch.object(
                millpy_fix, "_forward_output", side_effect=mock_forward_output
            ),
            unittest.mock.patch.object(
                millpy_fix._implementer_claude, "run",
                return_value=(
                    '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                    "fake",
                ),
            ),
        ):
            rc, out = self._run_main([
                "--scope", "holistic",
                "--review-file", str(self.review_file),
            ])

        self.assertEqual(rc, 0)
        self.assertEqual(captured_kwargs.get("verify_cmd"), "(exit 0) && (exit 0)")
        self.assertEqual(captured_kwargs.get("cwd_override"), nested_hub)

    def test_holistic_scope_mixed_cwd_raises_value_error_naming_batches(self):
        """Holistic scope: batches resolving to mixed cwd values raise ValueError naming the conflict (Card 20)."""
        nested_hub = self.tmp_path / "hub"
        nested_hub.mkdir(parents=True, exist_ok=True)
        _make_fixture(nested_hub)

        plan_dir = nested_hub / "_mill" / "plan"
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
        # batch1 pins its verify to the (nested) hub; batch2 pins its verify to the
        # git root -- a single joined shell command cannot honor both cwds at once.
        (plan_dir / "01-batch1.md").write_text(
            "```yaml\nverify:\n  cwd: hub\n  command: exit 0\n```\n\n# Batch: batch1\n",
            encoding="utf-8",
        )
        (plan_dir / "02-batch2.md").write_text(
            "```yaml\nverify:\n  cwd: git_root\n  command: exit 0\n```\n\n# Batch: batch2\n",
            encoding="utf-8",
        )

        # status_path now gates iter_batch_verifies on approval state -- both
        # batches must be "approved" for their verify commands to survive the
        # filter and reach the holistic join, matching the pre-status_path
        # unfiltered behavior this test exercises.
        nested_status_path = nested_hub / "_mill" / "status.md"
        millpy_fix._status.init_batches(nested_status_path, ["batch1", "batch2"])
        millpy_fix._status.set_batch_field(nested_status_path, "batch1", "state", "approved")
        millpy_fix._status.set_batch_field(nested_status_path, "batch2", "state", "approved")

        with (
            unittest.mock.patch.object(
                millpy_fix._paths, "resolve_hub_path", return_value=nested_hub
            ),
            # The rebind (Card 10) supersedes resolve_hub_path's value with
            # resolve_active_hub's for project_root -- override it here too so
            # this nested-hub simulation still resolves project_root to nested_hub.
            unittest.mock.patch.object(
                millpy_fix._paths, "resolve_active_hub", return_value=nested_hub
            ),
            unittest.mock.patch.object(
                millpy_fix._implementer_claude, "run",
                return_value=(
                    '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                    "fake",
                ),
            ),
        ):
            with self.assertRaises(ValueError) as ctx:
                self._run_main([
                    "--scope", "holistic",
                    "--review-file", str(self.review_file),
                ])

        message = str(ctx.exception)
        self.assertIn("batch1", message)
        self.assertIn("batch2", message)

    def test_resolve_holistic_verify_wraps_each_command_in_own_subshell(self):
        """Each contributing batch's command is wrapped in its own subshell before joining (bug1)."""
        joined_command, cwd_override = millpy_fix._resolve_holistic_verify([
            ("batch-a", "cd plugins/prowler && go test ./...", None),
            ("batch-b", "bash plugins/prowler/scripts/selftest.sh", None),
        ])

        self.assertEqual(
            joined_command,
            "(cd plugins/prowler && go test ./...) && (bash plugins/prowler/scripts/selftest.sh)",
        )
        self.assertIsNone(cwd_override)

    def test_resolve_holistic_verify_single_batch_still_wrapped(self):
        """A single contributing batch is still wrapped in parens, with no bare `&&` needed (bug1)."""
        joined_command, cwd_override = millpy_fix._resolve_holistic_verify([
            ("batch-a", "echo hi", None),
        ])

        self.assertEqual(joined_command, "(echo hi)")
        self.assertIsNone(cwd_override)

    def test_finalize_stage_batch_not_found_cwd_override_stays_none(self):
        """Finalize stage regression: batch_entry is None keeps cwd_override at pre-initialized None, not a NameError (Card 19)."""
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8",
        )

        captured_kwargs = {}

        def mock_finalize_from_output(agent_output_path_arg, project_root, **kwargs):
            captured_kwargs.update(kwargs)
            return 0

        with unittest.mock.patch.object(
            millpy_fix, "finalize_from_output", side_effect=mock_finalize_from_output
        ):
            rc, out = self._run_main([
                "--scope", "batch",
                "--batch-name", "nonexistent-batch",
                "--review-file", str(self.review_file),
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        self.assertIsNone(captured_kwargs.get("verify_cmd"))
        self.assertIsNone(captured_kwargs.get("cwd_override"))

    def test_finalize_stage_holistic_empty_batch_verifies_cwd_override_stays_none(self):
        """Finalize stage regression: holistic scope with empty batch_verifies keeps cwd_override at None (Card 19/20)."""
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8",
        )

        captured_kwargs = {}

        def mock_finalize_from_output(agent_output_path_arg, project_root, **kwargs):
            captured_kwargs.update(kwargs)
            return 0

        with unittest.mock.patch.object(
            millpy_fix, "finalize_from_output", side_effect=mock_finalize_from_output
        ):
            rc, out = self._run_main([
                "--scope", "holistic",
                "--review-file", str(self.review_file),
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        self.assertIsNone(captured_kwargs.get("verify_cmd"))
        self.assertIsNone(captured_kwargs.get("cwd_override"))

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
