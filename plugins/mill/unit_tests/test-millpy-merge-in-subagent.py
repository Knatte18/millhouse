"""Unit tests for millpy-merge-in-subagent.py CLI main().

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
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _implementer_common  # noqa: E402

_SCRIPT_PATH = HUB / "plugins" / "mill" / "scripts" / "millpy-merge-in-subagent.py"

_spec = importlib.util.spec_from_file_location("millpy_merge_in_subagent", str(_SCRIPT_PATH))
millpy_merge_in_subagent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(millpy_merge_in_subagent)


class TestMillpyMergeInSubagent(unittest.TestCase):

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp_path, ignore_errors=True)

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

    def _run_main(self, argv):
        """Run main(argv) with stdout captured. Returns (rc, captured_stdout)."""
        buf = io.StringIO()
        with unittest.mock.patch("sys.stdout", buf):
            rc = millpy_merge_in_subagent.main(argv)
        return rc, buf.getvalue()

    # ---- conflicts mode ----

    def test_1_conflicts_success(self):
        """conflicts mode: sub-agent returns success → exit 0, success JSON."""
        with unittest.mock.patch.object(
            millpy_merge_in_subagent._render, "render",
            return_value="rendered",
        ) as mock_render, \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_sonnet, "run",
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
        """conflicts mode: sub-agent returns stuck → exit 0, stuck JSON."""
        with unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_sonnet, "run",
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
        """conflicts mode: --files absent → exit 1, no JSON on stdout."""
        rc, out = self._run_main(["--mode", "conflicts"])
        self.assertEqual(rc, 1)
        self.assertEqual(out.strip(), "")

    def test_4_conflicts_llm_error(self):
        """conflicts mode: LLMError from sub-agent → exit 1, transient stuck JSON."""
        with unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_sonnet, "run",
            side_effect=millpy_merge_in_subagent._llm_claude.LLMError("quota"),
        ):
            rc, out = self._run_main(["--mode", "conflicts", "--files", "a.py"])

        self.assertEqual(rc, 1)
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "transient")

    # ---- verify-fix mode ----

    def test_5_verify_fix_success_no_subagent(self):
        """verify-fix mode: verify passes on first run → exit 0, success JSON, sub-agent not called."""
        with unittest.mock.patch.object(
            millpy_merge_in_subagent.subprocess, "run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ), \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._subprocess_util, "run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="abc1234\n", stderr=""),
        ), \
        unittest.mock.patch.object(
            millpy_merge_in_subagent._implementer_sonnet, "run",
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
        """verify-fix mode: verify fails → sub-agent dispatched, returns success."""
        # call 1 (verify cmd, shell=True): subprocess.run; calls 2+3 (git diff, git rev-parse): _subprocess_util.run
        with unittest.mock.patch.object(
            millpy_merge_in_subagent._render, "render",
            return_value="rendered",
        ) as mock_render, \
        unittest.mock.patch.object(
            millpy_merge_in_subagent.subprocess, "run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="FAILED test_foo", stderr=""
            ),
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
            millpy_merge_in_subagent._implementer_sonnet, "run",
            return_value=('{"status":"success","commit_sha":"abc"}\n', "fake"),
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
        """verify-fix mode: verify fails, sub-agent returns stuck → exit 0, stuck JSON."""
        # call 1 (verify cmd, shell=True): subprocess.run; calls 2+3 (git diff, git rev-parse): _subprocess_util.run
        with unittest.mock.patch.object(
            millpy_merge_in_subagent.subprocess, "run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="FAILED test_foo", stderr=""
            ),
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
            millpy_merge_in_subagent._implementer_sonnet, "run",
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
        """verify-fix mode: --cmd absent → exit 1, no JSON on stdout."""
        rc, out = self._run_main(["--mode", "verify-fix", "--checkpoint", "chk"])
        self.assertEqual(rc, 1)
        self.assertEqual(out.strip(), "")

    # ---- shared ----

    def test_9_missing_mode(self):
        """--mode absent → argparse SystemExit(2)."""
        with self.assertRaises(SystemExit) as cm:
            millpy_merge_in_subagent.main([])
        self.assertEqual(cm.exception.code, 2)

    def test_10_missing_slug(self):
        """MarkerError from slug_from_branch → exit 1."""
        with unittest.mock.patch.object(
            millpy_merge_in_subagent._marker, "slug_from_branch",
            side_effect=millpy_merge_in_subagent._marker.MarkerError("no slug"),
        ):
            rc, _ = self._run_main(["--mode", "conflicts", "--files", "f.py"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
