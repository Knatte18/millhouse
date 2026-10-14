"""Unit tests for millpy-verify-run.py CLI main().

Loads the module under test via importlib and calls main(argv) in-process.
Path resolution and config loading are patched to a temp dir; the verify commands are real
short-lived children.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _safe_rmtree  # noqa: E402
import _status  # noqa: E402

_SCRIPT_PATH = HUB / "plugins" / "mill" / "scripts" / "millpy-verify-run.py"

_spec = importlib.util.spec_from_file_location("millpy_verify_run", str(_SCRIPT_PATH))
millpy_verify_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(millpy_verify_run)

_JSON_KEYS = {
    "label", "cmd", "exit_code", "wall_s", "first_run", "timed_out", "output_path", "verify_runs",
}


class TestMillpyVerifyRun(unittest.TestCase):

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())
        self.addCleanup(
            _safe_rmtree.safe_rmtree, self.tmp_path, allowed_root=self.tmp_path, ignore_errors=True
        )
        self.status_path = self.tmp_path / "_mill" / "status.md"
        self.status_path.parent.mkdir(parents=True)
        self.status_path.write_text("# Status\n", encoding="utf-8")
        self.cfg = {"paths": {"status_md": "_mill/status.md"}}

        for target, attr, kwargs in (
            (millpy_verify_run._paths, "resolve_git_root", {"return_value": self.tmp_path}),
            (millpy_verify_run._paths, "resolve_hub_path", {"return_value": self.tmp_path}),
            (millpy_verify_run._config, "load_config", {"side_effect": lambda *_: self.cfg}),
        ):
            patcher = unittest.mock.patch.object(target, attr, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _script_command(self, body: str) -> str:
        """Return a bash-safe command running ``body`` as a Python script in the temp dir."""
        script = self.tmp_path / "child.py"
        script.write_text(body, encoding="utf-8")
        interpreter = Path(sys.executable).as_posix()
        return f'"{interpreter}" "{script.as_posix()}"'

    def _run_main(self, label: str, cmd: str):
        """Run main with captured stdout and stderr; return (rc, parsed JSON line)."""
        out_buf = io.StringIO()
        with unittest.mock.patch("sys.stdout", out_buf), unittest.mock.patch(
            "sys.stderr", io.StringIO()
        ):
            rc = millpy_verify_run.main(
                ["--label", label, "--cmd", cmd, "--cwd", str(self.tmp_path)]
            )
        return rc, json.loads(out_buf.getvalue().strip())

    def test_passing_command_exits_0_without_reason(self):
        rc, data = self._run_main("merge-in:batch-1", self._script_command("print('ok')\n"))

        self.assertEqual(rc, 0)
        self.assertEqual(set(data), _JSON_KEYS)
        self.assertEqual(data["label"], "merge-in:batch-1")
        self.assertEqual(data["exit_code"], 0)
        self.assertIs(data["timed_out"], False)
        self.assertIsInstance(data["output_path"], str)
        self.assertEqual(len(data["verify_runs"]), 1)
        self.assertEqual(data["verify_runs"][0]["label"], "merge-in:batch-1")

    def test_failing_command_exits_1_with_output_pointer_reason(self):
        rc, data = self._run_main(
            "merge-in:batch-1", self._script_command("import sys\nprint('boom')\nsys.exit(3)\n")
        )

        self.assertEqual(rc, 1)
        self.assertEqual(data["exit_code"], 3)
        self.assertIn("boom", data["reason"])
        self.assertTrue(data["reason"].endswith(f"[verify output: {data['output_path']}]"))

    def test_timeout_exits_1_with_timeout_prefix(self):
        self.cfg["pipeline"] = {"verify_timeout_minutes": 0.02}

        rc, data = self._run_main(
            "merge-in:slow", self._script_command("import time\ntime.sleep(30)\n")
        )

        self.assertEqual(rc, 1)
        self.assertIs(data["timed_out"], True)
        self.assertIsNone(data["exit_code"])
        self.assertTrue(data["reason"].startswith("[verify timed out after 1s: merge-in:slow] "))

    def test_invalid_timeout_exits_1_naming_the_config_key(self):
        self.cfg["pipeline"] = {"verify_timeout_minutes": 0}

        rc, data = self._run_main("merge-in:batch-1", self._script_command("print('ok')\n"))

        self.assertEqual(rc, 1)
        self.assertIn("pipeline.verify_timeout_minutes", data["reason"])
        self.assertEqual(data["label"], "merge-in:batch-1")

    def test_each_run_appends_one_verify_log_row(self):
        command = self._script_command("print('ok')\n")

        self._run_main("merge-in:first", command)
        self.assertEqual(len(_status.read_verify_log_rows(self.status_path)), 1)

        self._run_main("merge-in:second", command)
        rows = _status.read_verify_log_rows(self.status_path)
        self.assertEqual(len(rows), 2)
        self.assertIn("merge-in:first", rows[0])
        self.assertIn("merge-in:second", rows[1])


if __name__ == "__main__":
    unittest.main()
