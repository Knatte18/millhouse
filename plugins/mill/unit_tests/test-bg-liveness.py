"""Unit tests for _bg.is_bg_worker_alive liveness probe.

Tests that is_bg_worker_alive correctly parses millpy-bg worker logs,
detects EXIT sentinels, probes process liveness via os.kill, and falls
back to log mtime staleness on Windows EINVAL.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _bg  # noqa: E402


class TestBgLiveness(unittest.TestCase):
    """Test cases for is_bg_worker_alive."""

    def test_log_missing(self) -> None:
        """Log file does not exist -> (False, None)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "nonexistent.log"
            alive, pid = _bg.is_bg_worker_alive(log_path)
            self.assertFalse(alive)
            self.assertIsNone(pid)

    def test_log_no_pid_line(self) -> None:
        """Log has no WORKER PID line -> (False, None)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            log_path.write_text("some unrelated text\n", encoding="utf-8")
            alive, pid = _bg.is_bg_worker_alive(log_path)
            self.assertFalse(alive)
            self.assertIsNone(pid)

    def test_log_with_exit(self) -> None:
        """Log has WORKER PID and EXIT line -> (False, pid)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            log_path.write_text(
                "[mill-bg] WORKER PID=12345 START 2026-05-17T15:00:00Z\n"
                "some output\n"
                "[mill-bg] EXIT 0\n",
                encoding="utf-8",
            )
            alive, pid = _bg.is_bg_worker_alive(log_path)
            self.assertFalse(alive)
            self.assertEqual(pid, 12345)

    def test_log_live_pid(self) -> None:
        """Log with current process PID, no EXIT -> (True, pid)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            current_pid = os.getpid()
            log_path.write_text(
                f"[mill-bg] WORKER PID={current_pid} START 2026-05-17T15:00:00Z\n"
                "some output\n",
                encoding="utf-8",
            )
            alive, pid = _bg.is_bg_worker_alive(log_path)
            self.assertTrue(alive)
            self.assertEqual(pid, current_pid)

    def test_log_dead_pid_no_exit(self) -> None:
        """Log with invalid PID, no EXIT, stale mtime -> (False, pid)."""
        # PID 99999999 is assumed invalid on any modern OS
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            log_path.write_text(
                "[mill-bg] WORKER PID=99999999 START 2026-05-17T15:00:00Z\n"
                "some output\n",
                encoding="utf-8",
            )
            # Backdate mtime so Windows EINVAL falls through to staleness check
            old_ts = time.time() - (_bg._STALE_LOG_SECONDS + 60)
            os.utime(log_path, (old_ts, old_ts))
            alive, pid = _bg.is_bg_worker_alive(log_path)
            self.assertFalse(alive)
            self.assertEqual(pid, 99999999)

    def test_log_live_pid_with_stale_mtime(self) -> None:
        """Log with current PID, no EXIT, stale mtime -> (True, pid) (mtime not checked if kill succeeds)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            current_pid = os.getpid()
            log_path.write_text(
                f"[mill-bg] WORKER PID={current_pid} START 2026-05-17T15:00:00Z\n"
                "some output\n",
                encoding="utf-8",
            )
            # Backdate mtime; the kill probe should succeed before mtime check
            old_ts = time.time() - (_bg._STALE_LOG_SECONDS + 60)
            os.utime(log_path, (old_ts, old_ts))
            alive, pid = _bg.is_bg_worker_alive(log_path)
            self.assertTrue(alive)
            self.assertEqual(pid, current_pid)

    def test_log_oserror_fallback_to_mtime(self) -> None:
        """Log with os.kill raising OSError falls back to mtime staleness check."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            pid_value = 99999999
            log_path.write_text(
                f"[mill-bg] WORKER PID={pid_value} START 2026-05-17T15:00:00Z\n"
                "some output\n",
                encoding="utf-8",
            )
            # Monkeypatch os.kill to raise OSError (WinError 87 / EINVAL shape)
            with unittest.mock.patch.object(_bg.os, "kill", side_effect=OSError(22, "Invalid parameter")):
                # Test case (a): fresh mtime -> (True, pid)
                with self.assertLogs(_bg.__name__, level="DEBUG") as cm:
                    alive, pid = _bg.is_bg_worker_alive(log_path)
                    self.assertTrue(alive)
                    self.assertEqual(pid, pid_value)
                # Verify debug breadcrumb was emitted
                self.assertEqual(len(cm.output), 1)
                self.assertIn("is_bg_worker_alive", cm.output[0])
                self.assertIn("os.kill", cm.output[0])
                self.assertIn("falling back to log-mtime staleness", cm.output[0])

            # Test case (b): stale mtime -> (False, pid)
            with unittest.mock.patch.object(_bg.os, "kill", side_effect=OSError(22, "Invalid parameter")):
                old_ts = time.time() - (_bg._STALE_LOG_SECONDS + 60)
                os.utime(log_path, (old_ts, old_ts))
                alive, pid = _bg.is_bg_worker_alive(log_path)
                self.assertFalse(alive)
                self.assertEqual(pid, pid_value)

    def test_systemerror_fallback_to_mtime(self) -> None:
        """Log with os.kill raising SystemError falls back to mtime staleness check."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            pid_value = 99999999
            log_path.write_text(
                f"[mill-bg] WORKER PID={pid_value} START 2026-05-17T15:00:00Z\n"
                "some output\n",
                encoding="utf-8",
            )
            # Monkeypatch os.kill to raise SystemError (chained Windows error)
            system_error = SystemError("built-in function kill returned a result with an exception set")
            with unittest.mock.patch.object(_bg.os, "kill", side_effect=system_error):
                # Test case (a): fresh mtime -> (True, pid)
                with self.assertLogs(_bg.__name__, level="DEBUG") as cm:
                    alive, pid = _bg.is_bg_worker_alive(log_path)
                    self.assertTrue(alive)
                    self.assertEqual(pid, pid_value)
                # Verify debug breadcrumb was emitted
                self.assertEqual(len(cm.output), 1)
                self.assertIn("is_bg_worker_alive", cm.output[0])
                self.assertIn("os.kill", cm.output[0])
                self.assertIn("falling back to log-mtime staleness", cm.output[0])

            # Test case (b): stale mtime -> (False, pid)
            with unittest.mock.patch.object(_bg.os, "kill", side_effect=system_error):
                old_ts = time.time() - (_bg._STALE_LOG_SECONDS + 60)
                os.utime(log_path, (old_ts, old_ts))
                alive, pid = _bg.is_bg_worker_alive(log_path)
                self.assertFalse(alive)
                self.assertEqual(pid, pid_value)


class TestCheckBgStatus(unittest.TestCase):
    """Test cases for check_bg_status single-shot status helper."""

    def test_check_bg_status_missing_log(self) -> None:
        """Missing log file -> ('dead', None)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "nonexistent.log"
            status, code_or_pid = _bg.check_bg_status(log_path)
            self.assertEqual(status, "dead")
            self.assertIsNone(code_or_pid)

    def test_check_bg_status_exit_found(self) -> None:
        """Log has [mill-bg] EXIT 0 -> ('exit', 0)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            log_path.write_text(
                "[mill-bg] WORKER PID=12345 START 2026-05-17T15:00:00Z\n"
                "some output\n"
                "[mill-bg] EXIT 0\n",
                encoding="utf-8",
            )
            status, code_or_pid = _bg.check_bg_status(log_path)
            self.assertEqual(status, "exit")
            self.assertEqual(code_or_pid, 0)

    def test_check_bg_status_running(self) -> None:
        """Worker alive, no EXIT -> ('running', pid)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            pid_value = 12345
            log_path.write_text(
                f"[mill-bg] WORKER PID={pid_value} START 2026-05-17T15:00:00Z\n"
                "some output\n",
                encoding="utf-8",
            )
            # Mock is_bg_worker_alive to report alive
            with unittest.mock.patch.object(_bg, "is_bg_worker_alive", return_value=(True, pid_value)):
                status, code_or_pid = _bg.check_bg_status(log_path)
                self.assertEqual(status, "running")
                self.assertEqual(code_or_pid, pid_value)

    def test_check_bg_status_dead_no_exit(self) -> None:
        """Worker dead, no EXIT, re-read still no EXIT -> ('dead', pid)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            pid_value = 99999999
            log_path.write_text(
                f"[mill-bg] WORKER PID={pid_value} START 2026-05-17T15:00:00Z\n"
                "some output\n",
                encoding="utf-8",
            )
            # Mock is_bg_worker_alive to report dead
            with unittest.mock.patch.object(_bg, "is_bg_worker_alive", return_value=(False, pid_value)):
                status, code_or_pid = _bg.check_bg_status(log_path)
                self.assertEqual(status, "dead")
                self.assertEqual(code_or_pid, pid_value)

    def test_check_bg_status_race_guard_exit_appears(self) -> None:
        """Race guard: worker dead, re-read shows EXIT -> ('exit', 0) not ('dead', pid)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            pid_value = 12345
            log_path.write_text(
                f"[mill-bg] WORKER PID={pid_value} START 2026-05-17T15:00:00Z\n"
                "some output\n",
                encoding="utf-8",
            )
            call_count = [0]

            def read_text_side_effect(self, *args, **kwargs):
                """On first call (from check_bg_status initial read), no EXIT. On re-read (race guard), EXIT present."""
                call_count[0] += 1
                if call_count[0] == 1:
                    return f"[mill-bg] WORKER PID={pid_value} START 2026-05-17T15:00:00Z\nsome output\n"
                else:
                    return f"[mill-bg] WORKER PID={pid_value} START 2026-05-17T15:00:00Z\nsome output\n[mill-bg] EXIT 0\n"

            with unittest.mock.patch.object(_bg, "is_bg_worker_alive", return_value=(False, pid_value)):
                with unittest.mock.patch.object(Path, "read_text", read_text_side_effect):
                    status, code_or_pid = _bg.check_bg_status(log_path)
                    self.assertEqual(status, "exit")
                    self.assertEqual(code_or_pid, 0)


if __name__ == "__main__":
    unittest.main()
