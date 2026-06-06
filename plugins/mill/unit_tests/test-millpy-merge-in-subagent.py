"""Unit tests for millpy-merge-in-subagent.py CLI main().

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
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _implementer_common  # noqa: E402
import _safe_rmtree  # noqa: E402

_SCRIPT_PATH = HUB / "plugins" / "mill" / "scripts" / "millpy-merge-in-subagent.py"

_spec = importlib.util.spec_from_file_location("millpy_merge_in_subagent", str(_SCRIPT_PATH))
millpy_merge_in_subagent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(millpy_merge_in_subagent)


class TestMillpyMergeInSubagent(unittest.TestCase):

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())
        self.addCleanup(_safe_rmtree.safe_rmtree, self.tmp_path, allowed_root=self.tmp_path, ignore_errors=True)

        millhouse_dir = self.tmp_path / ".millhouse"
        millhouse_dir.mkdir(parents=True, exist_ok=True)
        (millhouse_dir / "config.local.yaml").write_text("{}", encoding="utf-8")

        wiki_dir = self.tmp_path / "wiki"
        wiki_dir.mkdir(parents=True, exist_ok=True)
        (wiki_dir / "config.yaml").write_text("merge:\n  verify_fix_rounds: 3\n", encoding="utf-8")

        self.original_cwd = os.getcwd()
        os.chdir(self.tmp_path)
        self.addCleanup(os.chdir, self.original_cwd)

        def _p(target, attr, **kwargs):
            patcher = unittest.mock.patch.object(target, attr, **kwargs)
            mock_obj = patcher.start()
            self.addCleanup(patcher.stop)
            return mock_obj

        self.mock_resolve_git_root = _p(
            millpy_merge_in_subagent._paths, "resolve_git_root",
            return_value=self.tmp_path,
        )
        self.mock_resolve_wiki = _p(
            millpy_merge_in_subagent._paths, "resolve_wiki_path",
            return_value=self.tmp_path / "wiki",
        )
        self.mock_load_config = _p(
            millpy_merge_in_subagent._review_common, "load_config",
            return_value={"merge": {"verify_fix_rounds": 3}, "llm": {"implementer_timeout": 1800}},
        )
        self.mock_slug_from_branch = _p(
            millpy_merge_in_subagent._marker, "slug_from_branch",
            return_value="test-slug",
        )
        self.mock_reviewers_load = _p(
            millpy_merge_in_subagent._reviewers, "load",
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
            millpy_merge_in_subagent._reviewers, "resolve",
            return_value={
                "type": "single",
                "provider": "claude",
                "model": "claude-sonnet-4-6",
                "effort": "high",
            },
        )
        import _implementer_common  # noqa: F401
        self.mock_compute_scope_violations = _p(
            _implementer_common._cleanliness, "compute_scope_violations",
            return_value=[],
        )

    def _run_main(self, argv):
        """Run main(argv) with stdout captured. Returns (rc, captured_stdout)."""
        buf = io.StringIO()
        with unittest.mock.patch("sys.stdout", buf):
            rc = millpy_merge_in_subagent.main(argv)
        return rc, buf.getvalue()

    # ---- conflicts mode ----

    def test_1_conflicts_success(self):
        """conflicts mode: sub-agent returns success -> exit 0, success JSON."""
        with unittest.mock.patch.object(
            millpy_merge_in_subagent._render, "render",
            return_value="rendered",
        ) as mock_render, \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run",
            return_value=('{"status":"success","commit_sha":"abc"}\n', "fake-session"),
        ), \
        unittest.mock.patch.object(
            _implementer_common._subprocess_util, "run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="abc1234\n", stderr=""
            ),
        ):
            rc, out = self._run_main(["--mode", "conflicts", "--files", "a.py", "b.py"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "success")

        call_args = mock_render.call_args
        values = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("values", {})
        self.assertIn("CONFLICTING_FILES", values)
        self.assertIn("`a.py`", values["CONFLICTING_FILES"])
        self.assertIn("`b.py`", values["CONFLICTING_FILES"])
        self.assertIn("PROJECT_ROOT", values)

    def test_2_conflicts_stuck(self):
        """conflicts mode: sub-agent returns stuck -> exit 0, stuck JSON."""
        with unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run",
            return_value=('{"status":"stuck","stuck_type":"logic","reason":"ambiguous"}\n', "fake"),
        ), \
        unittest.mock.patch.object(
            _implementer_common._subprocess_util, "run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="abc1234\n", stderr=""
            ),
        ):
            rc, out = self._run_main(["--mode", "conflicts", "--files", "a.py"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "logic")

    def test_3_conflicts_no_files(self):
        """conflicts mode: --files absent -> exit 1, no JSON on stdout."""
        rc, out = self._run_main(["--mode", "conflicts"])
        self.assertEqual(rc, 1)
        self.assertEqual(out.strip(), "")

    def test_4_conflicts_llm_error(self):
        """conflicts mode: LLMError from sub-agent -> exit 1, transient stuck JSON."""
        with unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run",
            side_effect=millpy_merge_in_subagent._llm_claude.LLMError("quota"),
        ):
            rc, out = self._run_main(["--mode", "conflicts", "--files", "a.py"])

        self.assertEqual(rc, 1)
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "transient")

    # ---- verify-fix mode ----

    def test_5_verify_fix_success_no_subagent(self):
        """verify-fix mode: verify passes on first run -> exit 0, success JSON, sub-agent not called."""
        with unittest.mock.patch.object(
            millpy_merge_in_subagent.subprocess, "run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ), \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._subprocess_util, "run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="abc1234\n", stderr=""),
        ), \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run",
        ) as mock_subagent:
            rc, out = self._run_main([
                "--mode", "verify-fix",
                "--cmd", "pytest tests/",
                "--checkpoint", "mill-checkpoint-x",
            ])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "success")
        mock_subagent.assert_not_called()

    def test_6_verify_fix_failure_subagent_success(self):
        """verify-fix mode: verify fails -> sub-agent dispatched, returns success."""
        # call 1 (initial verify, shell=True): subprocess.run
        # call 2 (post-verify, shell=True): subprocess.run
        # call 3 (git diff): _subprocess_util.run; call 4 (git rev-parse for post-verify success): _subprocess_util.run
        with unittest.mock.patch.object(
            millpy_merge_in_subagent._render, "render",
            return_value="rendered",
        ) as mock_render, \
        unittest.mock.patch.object(
            millpy_merge_in_subagent.subprocess, "run",
            side_effect=[
                subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="FAILED test_foo", stderr=""
                ),
                subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ],
        ), \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._subprocess_util, "run",
            side_effect=[
                subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="diff --git a/f.py...", stderr=""
                ),
                subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="abc1234\n", stderr=""
                ),
            ],
        ), \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run",
            return_value=("", "fake-session"),
        ):
            rc, out = self._run_main([
                "--mode", "verify-fix",
                "--cmd", "pytest tests/",
                "--checkpoint", "mill-checkpoint-x",
            ])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "success")

        call_args = mock_render.call_args
        values = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("values", {})
        self.assertIn("VERIFY_OUTPUT", values)
        self.assertIn("FAILED test_foo", values["VERIFY_OUTPUT"])
        self.assertEqual(values.get("VERIFY_CMD"), "pytest tests/")
        self.assertEqual(values.get("VERIFY_FIX_ROUNDS"), "3")

    def test_7_verify_fix_subagent_stuck(self):
        """verify-fix mode: verify fails, sub-agent returns stuck -> exit 0, stuck JSON."""
        # call 1 (initial verify, shell=True): subprocess.run
        # call 2 (post-verify, shell=True): subprocess.run
        # call 3 (git diff): _subprocess_util.run; call 4 (git rev-parse for _forward_output): _subprocess_util.run
        with unittest.mock.patch.object(
            millpy_merge_in_subagent.subprocess, "run",
            side_effect=[
                subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="FAILED test_foo", stderr=""
                ),
                subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="FAILED test_foo", stderr=""
                ),
            ],
        ), \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._subprocess_util, "run",
            side_effect=[
                subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="diff --git a/f.py...", stderr=""
                ),
                subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="abc1234\n", stderr=""
                ),
            ],
        ), \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run",
            return_value=(
                '{"status":"stuck","stuck_type":"verify","reason":"still failing"}\n',
                "fake",
            ),
        ):
            rc, out = self._run_main([
                "--mode", "verify-fix",
                "--cmd", "pytest tests/",
                "--checkpoint", "chk",
            ])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "verify")

    def test_8_verify_fix_missing_cmd(self):
        """verify-fix mode: --cmd absent -> exit 1, no JSON on stdout."""
        rc, out = self._run_main(["--mode", "verify-fix", "--checkpoint", "chk"])
        self.assertEqual(rc, 1)
        self.assertEqual(out.strip(), "")

    def test_11_verify_fix_failure_subagent_no_json_post_verify_success(self):
        """verify-fix mode: verify fails, sub-agent emits no JSON, post-verify passes -> success."""
        with unittest.mock.patch.object(
            millpy_merge_in_subagent.subprocess, "run",
            side_effect=[
                subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="FAILED test_foo", stderr=""
                ),
                subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ],
        ), \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._subprocess_util, "run",
            side_effect=[
                subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="diff --git a/f.py...", stderr=""
                ),
                subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="abc1234\n", stderr=""
                ),
            ],
        ), \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run",
            return_value=("", "fake"),
        ), \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._render, "render",
            return_value="rendered",
        ):
            rc, out = self._run_main(["--mode", "verify-fix", "--cmd", "pytest tests/", "--checkpoint", "chk"])

        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.strip())["status"], "success")

    # ---- shared ----

    def test_9_missing_mode(self):
        """--mode absent -> argparse SystemExit(2)."""
        with self.assertRaises(SystemExit) as cm:
            millpy_merge_in_subagent.main([])
        self.assertEqual(cm.exception.code, 2)

    def test_10_missing_slug(self):
        """MarkerError from slug_from_branch -> exit 1."""
        with unittest.mock.patch.object(
            millpy_merge_in_subagent._marker, "slug_from_branch",
            side_effect=millpy_merge_in_subagent._marker.MarkerError("no slug"),
        ):
            rc, _ = self._run_main(["--mode", "conflicts", "--files", "f.py"])
        self.assertEqual(rc, 1)

    def test_12_stage_prepare_conflicts(self):
        """--stage prepare conflicts mode: renders brief, calls emit_prepare, no LLM call."""
        with unittest.mock.patch.object(millpy_merge_in_subagent._render, "render", return_value="Brief text"):
            with unittest.mock.patch.object(
                millpy_merge_in_subagent._implementer_claude, "run"
            ) as mock_run:
                rc, out = self._run_main(["--mode", "conflicts", "--files", "f.py", "--stage", "prepare"])

        self.assertEqual(rc, 0)
        # LLM should not be called in prepare stage
        mock_run.assert_not_called()
        # Output should be prepare JSON envelope
        data = json.loads(out.strip())
        self.assertEqual(data["stage"], "prepare")
        self.assertEqual(data["role"], "merge")
        self.assertEqual(data["scope"], "conflicts")

    def test_13_stage_prepare_verify_fix_passes(self):
        """--stage prepare verify-fix mode: verify passes -> dispatch_needed:false with embedded envelope."""
        verify_cmd = "exit 0"
        with unittest.mock.patch("subprocess.run") as mock_subprocess:
            # Verify passes (returncode=0)
            mock_subprocess.return_value = unittest.mock.MagicMock(
                returncode=0, stdout="", stderr=""
            )
            with unittest.mock.patch.object(
                millpy_merge_in_subagent._subprocess_util, "run",
                return_value=unittest.mock.MagicMock(returncode=0, stdout="abc123\n"),
            ):
                with unittest.mock.patch.object(
                    millpy_merge_in_subagent._implementer_claude, "run"
                ) as mock_run:
                    rc, out = self._run_main([
                        "--mode", "verify-fix",
                        "--cmd", verify_cmd,
                        "--checkpoint", "abc123",
                        "--stage", "prepare",
                    ])

        self.assertEqual(rc, 0)
        # LLM should not be called when verify passes in prepare
        mock_run.assert_not_called()
        # Output should be prepare JSON with dispatch_needed:false
        data = json.loads(out.strip())
        self.assertEqual(data["stage"], "prepare")
        self.assertEqual(data["dispatch_needed"], False)
        self.assertIn("envelope", data)
        self.assertEqual(data["envelope"]["status"], "success")

    def test_14_stage_prepare_verify_fix_fails(self):
        """--stage prepare verify-fix mode: verify fails -> normal prepare with dispatch_needed:true."""
        verify_cmd = "exit 1"
        with unittest.mock.patch("subprocess.run") as mock_subprocess:
            # Verify fails (returncode=1)
            mock_subprocess.return_value = unittest.mock.MagicMock(
                returncode=1, stdout="error", stderr=""
            )
            with unittest.mock.patch.object(
                millpy_merge_in_subagent._subprocess_util, "run",
                return_value=unittest.mock.MagicMock(returncode=0, stdout="abc123\n"),
            ):
                with unittest.mock.patch.object(millpy_merge_in_subagent._render, "render", return_value="Brief text"):
                    with unittest.mock.patch.object(
                        millpy_merge_in_subagent._implementer_claude, "run"
                    ) as mock_run:
                        rc, out = self._run_main([
                            "--mode", "verify-fix",
                            "--cmd", verify_cmd,
                            "--checkpoint", "abc123",
                            "--stage", "prepare",
                        ])

        self.assertEqual(rc, 0)
        # LLM should not be called in prepare stage
        mock_run.assert_not_called()
        # Output should be prepare JSON with normal envelope
        data = json.loads(out.strip())
        self.assertEqual(data["stage"], "prepare")
        self.assertEqual(data["role"], "merge")
        self.assertEqual(data["scope"], "verify-fix")

    def test_15_stage_finalize_conflicts(self):
        """--stage finalize conflicts mode: reads agent output, calls finalize_from_output."""
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz"}\n',
            encoding="utf-8"
        )

        with unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run"
        ) as mock_run:
            rc, out = self._run_main([
                "--mode", "conflicts",
                "--files", "f.py",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        # LLM should not be called in finalize stage
        mock_run.assert_not_called()
        # Output should be the agent output processed by _forward_output
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "success")

    def test_16_stage_finalize_verify_fix_reruns_verify(self):
        """--stage finalize verify-fix mode: re-runs verify, returns success if it passes."""
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text("agent output", encoding="utf-8")
        verify_cmd = "exit 0"

        with unittest.mock.patch("subprocess.run") as mock_subprocess:
            # Verify passes on re-run (returncode=0)
            mock_subprocess.return_value = unittest.mock.MagicMock(
                returncode=0, stdout="", stderr=""
            )
            with unittest.mock.patch.object(
                millpy_merge_in_subagent._subprocess_util, "run",
                return_value=unittest.mock.MagicMock(returncode=0, stdout="abc123\n"),
            ):
                with unittest.mock.patch.object(
                    millpy_merge_in_subagent._implementer_claude, "run"
                ) as mock_run:
                    rc, out = self._run_main([
                        "--mode", "verify-fix",
                        "--cmd", verify_cmd,
                        "--checkpoint", "abc123",
                        "--stage", "finalize",
                        "--agent-output", str(agent_output_path),
                    ])

        self.assertEqual(rc, 0)
        # LLM should not be called in finalize stage
        mock_run.assert_not_called()
        # Output should be success JSON
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "success")


if __name__ == "__main__":
    unittest.main()
