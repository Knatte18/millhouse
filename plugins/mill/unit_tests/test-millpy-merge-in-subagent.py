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


def _clean_gate_side_effect(argv, **kwargs):
    """Realistic ``_subprocess_util.run`` side_effect covering every call this module makes.

    ``git rev-parse HEAD`` returns a fake sha (the pre-existing constant every test relied on).
    Both marker-gate checks the Card 6 helper issues -- ``git diff --name-only --diff-filter=U ...``
    and ``git diff --cached --check ...`` -- get their own realistic clean response (empty stdout,
    returncode 0) instead of reusing the rev-parse sha by coincidence, so a conflicts-mode success
    test genuinely exercises a passing gate rather than happening to pass because the sha string
    contains neither "conflict marker" nor any of the test's input filenames.
    """
    if "rev-parse" in argv:
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout="a" * 40 + "\n", stderr=""
        )
    return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")


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
        self.mock_resolve_container_path = _p(
            millpy_merge_in_subagent._paths, "resolve_container_path",
            return_value=self.tmp_path.parent,
        )
        self.mock_resolve_active_hub = _p(
            millpy_merge_in_subagent._paths, "resolve_active_hub",
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
            side_effect=_clean_gate_side_effect,
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
        # call 1 (initial verify, shell=True): subprocess.run call 2 (post-verify, shell=True): subprocess.run call 3 (git diff): _subprocess_util.run;
        # call 4 (git rev-parse for post-verify success): _subprocess_util.run
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
        # call 1 (initial verify, shell=True): subprocess.run call 2 (post-verify, shell=True): subprocess.run call 3 (git diff): _subprocess_util.run;
        # call 4 (git rev-parse for _forward_output): _subprocess_util.run
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
        """--mode absent (and --recompute-baseline not set) -> exit 1, no SystemExit.

        --mode is not an argparse-required flag (--recompute-baseline is a valid alternative), so
        main() validates this manually with a print + return 1 rather than raising SystemExit --
        unlike an argparse-required argument.
        """
        stderr_buf = io.StringIO()
        with unittest.mock.patch("sys.stderr", stderr_buf):
            rc = millpy_merge_in_subagent.main([])
        self.assertEqual(rc, 1)
        self.assertIn("--mode is required unless --recompute-baseline is set", stderr_buf.getvalue())

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
        self.assertEqual(data["effort"], "high")

    def test_project_root_rebind_uses_resolve_active_hub_not_raw_cwd(self):
        """project_root rebinds to resolve_active_hub's value, not the raw Path.cwd() this file used
        before.

        This file's pre-fix project_root binding was a raw Path.cwd() -- no .millhouse walk at all.
        Overriding resolve_active_hub to a decoy directory distinct from self.tmp_path (the value
        Path.cwd() would still resolve to, since setUp chdir's there) simulates the corrected active
        task worktree.
        briefs_dir (surfaced via --stage prepare conflicts mode's brief_path in the envelope) must
        resolve under the decoy, proving project_root was rebound via the captured slug and
        resolve_active_hub, not left at cwd.
        """
        corrected_root = self.tmp_path / "corrected-worktree"
        (corrected_root / "_mill" / "briefs").mkdir(parents=True, exist_ok=True)
        self.mock_resolve_active_hub.return_value = corrected_root

        with unittest.mock.patch.object(millpy_merge_in_subagent._render, "render", return_value="Brief text"):
            with unittest.mock.patch.object(
                millpy_merge_in_subagent._implementer_claude, "run"
            ) as mock_run:
                rc, out = self._run_main(["--mode", "conflicts", "--files", "f.py", "--stage", "prepare"])

        self.assertEqual(rc, 0)
        mock_run.assert_not_called()
        data = json.loads(out.strip())
        brief_path = Path(data["brief_path"])
        self.assertEqual(brief_path.parent, corrected_root / "_mill" / "briefs")
        self.assertFalse(brief_path.is_relative_to(self.tmp_path / "_mill" / "briefs"))

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
        self.assertEqual(data["effort"], "high")

    def test_15_stage_finalize_conflicts(self):
        """--stage finalize conflicts mode: reads agent output, calls finalize_from_output."""
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz"}\n',
            encoding="utf-8"
        )

        with unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run"
        ) as mock_run, \
        unittest.mock.patch.object(
            _implementer_common._subprocess_util, "run",
            side_effect=_clean_gate_side_effect,
        ):
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

    def test_16_conflicts_discarded_field_preserved(self):
        """conflicts mode: success verdict with discarded field is forwarded intact.

        Pins the contract that _forward_output prints the full parsed dict verbatim, so an optional
        discarded list emitted by the conflict sub-agent is not stripped.
        """
        with unittest.mock.patch.object(
            millpy_merge_in_subagent._render, "render",
            return_value="rendered",
        ), \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run",
            # Sub-agent emits success with a non-empty discarded list
            return_value=(
                '{"status":"success","discarded":["column B of table row 3 from ours side"]}\n',
                "fake-session",
            ),
        ), \
        unittest.mock.patch.object(
            _implementer_common._subprocess_util, "run",
            side_effect=_clean_gate_side_effect,
        ):
            rc, out = self._run_main(["--mode", "conflicts", "--files", "a.py"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "success")
        # discarded field must be present and non-empty -- the forwarding path must not strip it
        self.assertIn("discarded", data)
        self.assertIsInstance(data["discarded"], list)
        self.assertGreater(len(data["discarded"]), 0)
        self.assertIn("column B", data["discarded"][0])

    def test_17_conflicts_success_no_discarded_is_clean(self):
        """conflicts mode: success verdict without discarded field emits clean success.

        Pins the contract that a conflict sub-agent that discarded nothing emits
        {"status":"success"} (no discarded key),
        and _forward_output passes it through unchanged.
        """
        with unittest.mock.patch.object(
            millpy_merge_in_subagent._render, "render",
            return_value="rendered",
        ), \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run",
            # Sub-agent emits plain success with no discarded field
            return_value=(
                '{"status":"success"}\n',
                "fake-session",
            ),
        ), \
        unittest.mock.patch.object(
            _implementer_common._subprocess_util, "run",
            side_effect=_clean_gate_side_effect,
        ):
            rc, out = self._run_main(["--mode", "conflicts", "--files", "a.py"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "success")
        # discarded must be absent (or empty) when the sub-agent did not report any
        discarded = data.get("discarded")
        self.assertTrue(
            discarded is None or discarded == [],
            f"Expected no discarded field or empty list, got: {discarded!r}",
        )

    def test_2x_conflicts_finalize_emits_pre_merge_head(self):
        """--stage finalize conflicts mode: the corrective SHA is emitted as pre_merge_head, not
        commit_sha (#953) -- HEAD at this point in the flow is still the pre-merge commit.
        """
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz"}\n',
            encoding="utf-8"
        )

        with unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run"
        ) as mock_run, \
        unittest.mock.patch.object(
            _implementer_common._subprocess_util, "run",
            side_effect=_clean_gate_side_effect,
        ):
            rc, out = self._run_main([
                "--mode", "conflicts",
                "--files", "f.py",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        mock_run.assert_not_called()
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "success")
        self.assertNotIn("commit_sha", data)
        self.assertEqual(data["pre_merge_head"], "a" * 40)

    def test_2x_conflicts_full_mode_emits_pre_merge_head(self):
        """Full-mode conflicts success: the corrective SHA is emitted as pre_merge_head, not
        commit_sha (#953), at the second conflicts-mode call site (_run_conflicts's own
        _forward_output return).
        """
        with unittest.mock.patch.object(
            millpy_merge_in_subagent._render, "render",
            return_value="rendered",
        ), \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run",
            return_value=(
                '{"status":"success"}\n',
                "fake-session",
            ),
        ), \
        unittest.mock.patch.object(
            _implementer_common._subprocess_util, "run",
            side_effect=_clean_gate_side_effect,
        ):
            rc, out = self._run_main(["--mode", "conflicts", "--files", "a.py"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "success")
        self.assertNotIn("commit_sha", data)
        self.assertEqual(data["pre_merge_head"], "a" * 40)

    def test_18_stage_finalize_verify_fix_reruns_verify(self):
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

    def test_19_finalize_conflicts_accepts_parity_flags(self):
        """
        conflicts finalize: --session-id/--start-sha/--round accepted without error, delegates to
        finalize_from_output with session_id=None.

        Regression test for #569: millpy-merge-in-subagent.py --stage finalize previously rejected
        --session-id (and the other envelope fields) that its own --stage prepare envelope emits via
        emit_prepare.
        The fix adds all three as accepted-but-ignored arguments so mill-go's generic "thread
        applicable prepare-envelope fields into finalize" logic is safe for this script.

        Asserts:
        - rc == 0 (argparse would raise SystemExit(2) on unrecognized arguments)
        - LLM is not invoked in the finalize stage
        - finalize_from_output is called exactly once to process the agent output
        - session_id=None is passed to finalize_from_output (the threaded value is ignored)
        """
        # Write an agent output file so --agent-output has a valid target.
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz"}\n',
            encoding="utf-8",
        )

        with unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run"
        ) as mock_llm, \
        unittest.mock.patch.object(
            # Patch finalize_from_output in the subagent module's namespace so we can assert it was called with the expected arguments without triggering real git operations on a non-repo temp directory.
            millpy_merge_in_subagent, "finalize_from_output",
            return_value=0,
        ) as mock_finalize, \
        unittest.mock.patch.object(
            # The gate now runs BEFORE finalize_from_output;
            # give it a clean response so control still reaches the mocked finalize_from_output call above instead of the real, unmocked git checks failing ("fatal: not a git repository") against the non-repo temp dir.
            _implementer_common._subprocess_util, "run",
            side_effect=_clean_gate_side_effect,
        ):
            rc, out = self._run_main([
                "--mode", "conflicts",
                "--files", "f.py",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
                "--session-id", "test-session-id",
                "--start-sha", "abc1234",
                "--round", "1",
            ])

        # rc must be 0 -- argparse raises SystemExit(2) on unrecognized arguments
        self.assertEqual(rc, 0)
        # LLM must not be invoked in the finalize stage
        mock_llm.assert_not_called()
        # finalize_from_output must be called to process the agent output
        mock_finalize.assert_called_once()
        # session_id must be None -- the threaded --session-id value is accepted but ignored;
        # conflicts-mode finalize always passes session_id=None to finalize_from_output
        _, call_kwargs = mock_finalize.call_args
        self.assertIsNone(call_kwargs.get("session_id"))

    def test_2x_stage_full_conflicts_reaches_gate(self):
        """--stage full: a positive marker-gate finding overrides the sub-agent's own success
        (#713).

        Proves Card 7 actually wires the gate in, not just that the helper (Card 9) works standalone
        -- the sub-agent self-reports success, but the mocked diff-filter=U check finds a.py still
        unmerged.
        """
        def _unmerged_side_effect(argv, **kwargs):
            if "--diff-filter=U" in argv:
                return subprocess.CompletedProcess(args=argv, returncode=0, stdout="a.py\n", stderr="")
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")

        with unittest.mock.patch.object(
            millpy_merge_in_subagent._render, "render",
            return_value="rendered",
        ), \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run",
            return_value=('{"status":"success","commit_sha":"abc"}\n', "fake-session"),
        ), \
        unittest.mock.patch.object(
            _implementer_common._subprocess_util, "run",
            side_effect=_unmerged_side_effect,
        ):
            rc, out = self._run_main(["--mode", "conflicts", "--files", "a.py"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "logic")
        self.assertIn("never staged", data["reason"])
        self.assertIn("a.py", data["reason"])

    def test_2x_stage_finalize_conflicts_reaches_gate(self):
        """--stage finalize: a positive marker-gate finding overrides the sub-agent's own success
        (#713).

        Proves Card 8 actually wires the gate in ahead of finalize_from_output -- the agent-output
        file self-reports success,
        but the mocked --cached --check finds a residual marker in f.py.
        """
        def _marker_side_effect(argv, **kwargs):
            if "--check" in argv:
                return subprocess.CompletedProcess(
                    args=argv, returncode=2, stdout="f.py:3: leftover conflict marker\n", stderr=""
                )
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")

        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz"}\n',
            encoding="utf-8",
        )

        with unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run"
        ) as mock_run, \
        unittest.mock.patch.object(
            _implementer_common._subprocess_util, "run",
            side_effect=_marker_side_effect,
        ):
            rc, out = self._run_main([
                "--mode", "conflicts",
                "--files", "f.py",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        mock_run.assert_not_called()
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "logic")
        self.assertIn("residual conflict markers", data["reason"])
        self.assertIn("f.py", data["reason"])

    def test_2x_stuck_status_skips_gate_stage_full(self):
        """--stage full: a sub-agent stuck self-report never triggers the marker gate (#713)."""
        with unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run",
            return_value=('{"status":"stuck","stuck_type":"logic","reason":"ambiguous"}\n', "fake"),
        ), \
        unittest.mock.patch.object(
            millpy_merge_in_subagent, "_verify_conflict_markers",
        ) as mock_gate:
            rc, out = self._run_main(["--mode", "conflicts", "--files", "a.py"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "stuck")
        mock_gate.assert_not_called()

    def test_2x_stuck_status_skips_gate_stage_finalize(self):
        """--stage finalize: an agent-output stuck self-report never triggers the marker gate (#713)."""
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"stuck","stuck_type":"logic","reason":"ambiguous"}\n',
            encoding="utf-8",
        )

        with unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_claude, "run"
        ) as mock_run, \
        unittest.mock.patch.object(
            millpy_merge_in_subagent, "_verify_conflict_markers",
        ) as mock_gate:
            rc, out = self._run_main([
                "--mode", "conflicts",
                "--files", "f.py",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        mock_run.assert_not_called()
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "stuck")
        mock_gate.assert_not_called()

    def test_2x_finalize_conflicts_missing_agent_output_file(self):
        """--stage finalize conflicts mode: missing --agent-output file -> exit 1, actionable
        message.

        Regression coverage for Card 8's own is_file() guard -- proves it fires before
        _extract_status_json / _verify_conflict_markers ever run on a missing file, rather than
        crashing with a raw traceback.
        """
        missing_path = self.tmp_path / "does-not-exist.txt"
        stderr_buf = io.StringIO()
        with unittest.mock.patch("sys.stderr", stderr_buf):
            rc = millpy_merge_in_subagent.main([
                "--mode", "conflicts",
                "--files", "a.py",
                "--stage", "finalize",
                "--agent-output", str(missing_path),
            ])
        self.assertEqual(rc, 1)
        self.assertIn("ERROR: --agent-output file not found", stderr_buf.getvalue())
        self.assertIn(str(missing_path), stderr_buf.getvalue())

    def test_2x_finalize_conflicts_missing_files_flag(self):
        """--stage finalize conflicts mode: --files omitted -> exit 1, actionable message.

        Regression coverage for Card 8's own falsy-`--files` guard -- proves the finalize early-exit
        branch never reaches _run_conflicts's own --files check at line 337.
        """
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz"}\n',
            encoding="utf-8",
        )
        stderr_buf = io.StringIO()
        with unittest.mock.patch("sys.stderr", stderr_buf):
            rc = millpy_merge_in_subagent.main([
                "--mode", "conflicts",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])
        self.assertEqual(rc, 1)
        self.assertIn("--files is required for conflicts mode", stderr_buf.getvalue())

    def test_20_recompute_baseline_missing_status_md(self):
        """--recompute-baseline with status.md absent -> exit 0, baseline:error JSON, no raise.

        setUp() never creates _mill/ under self.tmp_path, so status.md is already absent by
        default here. load_config's mocked return_value must carry a realistic "paths" section
        (mirroring real mill-config.yaml) so require_status_path raises the genuine TaskHubError
        this bug is about, rather than an unrelated KeyError from a paths-less test fixture.
        """
        self.mock_load_config.return_value = {
            "merge": {"verify_fix_rounds": 3},
            "llm": {"implementer_timeout": 1800},
            "paths": {"status_md": "_mill/status.md", "plan_dir": "_mill/plan/"},
        }
        rc, out = self._run_main(["--recompute-baseline"])
        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["baseline"], "error")
        self.assertIn("status.md", data["reason"])


def _git(args, cwd, check=True):
    """Run a git subprocess against a real fixture repo, raising on unexpected failure."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stdout}{result.stderr}")
    return result


class TestVerifyConflictMarkersGate(unittest.TestCase):
    """Exercises _verify_conflict_markers directly against real git repositories (#713).

    Unlike TestMillpyMergeInSubagent, most of these tests do NOT mock _subprocess_util.run -- the
    helper's own two git invocations are exactly what needs proving against a real
    conflicted/resolved repo.
    Only the "fatal:" scenario mocks _subprocess_util.run, since forcing a real git lock-contention
    failure is impractical to fixture reliably.
    """

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(_safe_rmtree.safe_rmtree, self.repo, allowed_root=self.repo, ignore_errors=True)
        _git(["init"], self.repo)
        _git(["checkout", "-b", "main"], self.repo)

    def _commit(self, message):
        _git(
            ["-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", message],
            self.repo,
        )

    def _write(self, name, content):
        (self.repo / name).write_text(content, encoding="utf-8")

    def _make_content_conflict(self, *filenames):
        """Seed a real content conflict across all ``filenames`` in one merge, left unresolved.

        All files conflict simultaneously via a single merge commit -- required for the multi-file
        scenario, where two different files must remain unresolved/staged independently in the same
        working tree at the same time.
        """
        branch = "side-" + "-".join(filenames).replace(".", "_")
        for filename in filenames:
            self._write(filename, "base\n")
            _git(["add", filename], self.repo)
        self._commit("base (" + ", ".join(filenames) + ")")

        _git(["checkout", "-b", branch], self.repo)
        for filename in filenames:
            self._write(filename, "base\nside change\n")
            _git(["add", filename], self.repo)
        self._commit("side change (" + ", ".join(filenames) + ")")

        _git(["checkout", "main"], self.repo)
        for filename in filenames:
            self._write(filename, "base\nmain change\n")
            _git(["add", filename], self.repo)
        self._commit("main change (" + ", ".join(filenames) + ")")

        # Expected to fail with a real content conflict -- markers land in the working tree.
        _git(["merge", branch], self.repo, check=False)

    def test_2x_marker_gate_residual_markers_staged(self):
        """(a) file staged via git add still carries residual markers -> stuck, names the file."""
        self._make_content_conflict("conflict.txt")
        # Stage the file exactly as merge left it -- markers still present -- simulating a sub-agent that ran `git add` without actually resolving the conflict.
        _git(["add", "conflict.txt"], self.repo)

        result = millpy_merge_in_subagent._verify_conflict_markers(["conflict.txt"], self.repo)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "stuck")
        self.assertEqual(result["stuck_type"], "logic")
        self.assertIn("residual conflict markers", result["reason"])
        self.assertIn("conflict.txt", result["reason"])

    def test_2x_marker_gate_never_staged(self):
        """(b) file left unmerged and never staged -> stuck, names the file."""
        self._make_content_conflict("conflict.txt")
        # Do NOT git add -- the file remains unmerged in the index.

        result = millpy_merge_in_subagent._verify_conflict_markers(["conflict.txt"], self.repo)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "stuck")
        self.assertEqual(result["stuck_type"], "logic")
        self.assertIn("never staged", result["reason"])
        self.assertIn("still unmerged", result["reason"])
        self.assertIn("conflict.txt", result["reason"])

    def test_2x_marker_gate_clean_resolved_and_staged(self):
        """(c) a clean, properly resolved-and-staged file -> None."""
        self._make_content_conflict("conflict.txt")
        # Resolve for real: overwrite with reconciled content, then stage it.
        self._write("conflict.txt", "base\nmain change\nside change\n")
        _git(["add", "conflict.txt"], self.repo)

        result = millpy_merge_in_subagent._verify_conflict_markers(["conflict.txt"], self.repo)
        self.assertIsNone(result)

    def test_2x_marker_gate_modify_delete_resolved_via_rm(self):
        """(d) modify/delete conflict resolved via `git rm` -> None, not an error."""
        self._write("d.py", "original\n")
        _git(["add", "d.py"], self.repo)
        self._commit("base (d.py)")

        _git(["checkout", "-b", "side-d"], self.repo)
        self._write("d.py", "changed\n")
        _git(["add", "d.py"], self.repo)
        self._commit("side modifies d.py")

        _git(["checkout", "main"], self.repo)
        _git(["rm", "d.py"], self.repo)
        self._commit("main deletes d.py")

        # Expected to conflict: deleted on main, modified on side.
        _git(["merge", "side-d"], self.repo, check=False)
        # Resolve by keeping the deletion.
        _git(["rm", "d.py"], self.repo)

        result = millpy_merge_in_subagent._verify_conflict_markers(["d.py"], self.repo)
        self.assertIsNone(result)

    def test_2x_marker_gate_multi_file_both_failure_shapes_in_one_call(self):
        """(e) one file trips check 1, a different file trips check 2, in a single call."""
        # Both files conflict in the same merge so they can be independently staged/left-unmerged afterward.
        self._make_content_conflict("never-staged.txt", "has-markers.txt")
        # Leave never-staged.txt unmerged; stage has-markers.txt as-is (markers still present).
        _git(["add", "has-markers.txt"], self.repo)

        result = millpy_merge_in_subagent._verify_conflict_markers(
            ["never-staged.txt", "has-markers.txt"], self.repo
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "stuck")
        self.assertEqual(result["stuck_type"], "logic")
        self.assertIn("never-staged.txt", result["reason"])
        self.assertIn("has-markers.txt", result["reason"])
        self.assertIn("never staged", result["reason"])
        self.assertIn("residual conflict markers", result["reason"])

    def test_2x_marker_gate_fatal_output_short_circuits(self):
        """(f) a "fatal:"-prefixed check output is distinct from an ordinary finding."""
        def _fake_run(argv, **kwargs):
            if "--diff-filter=U" in argv:
                return subprocess.CompletedProcess(
                    args=argv, returncode=128, stdout="", stderr="fatal: unable to read tree\n"
                )
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")

        with unittest.mock.patch.object(
            millpy_merge_in_subagent._subprocess_util, "run", side_effect=_fake_run
        ):
            result = millpy_merge_in_subagent._verify_conflict_markers(["a.py"], self.repo)

        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "stuck")
        self.assertEqual(result["stuck_type"], "logic")
        self.assertIn("verification itself failed to run", result["reason"])
        # Distinct from an ordinary marker/unmerged finding.
        self.assertNotIn("never staged", result["reason"])
        self.assertNotIn("residual conflict markers", result["reason"])


if __name__ == "__main__":
    unittest.main()
