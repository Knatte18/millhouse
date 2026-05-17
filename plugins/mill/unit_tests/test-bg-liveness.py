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


if __name__ == "__main__":
    unittest.main()
