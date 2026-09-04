"""Unit tests for _bg.is_bg_worker_alive liveness probe.

Tests that is_bg_worker_alive correctly parses millpy-bg worker logs, detects EXIT sentinels, probes
process liveness via os.kill, and falls back to log mtime staleness on Windows EINVAL.
Also covers _win_pid_alive, the non-destructive ctypes-based Windows liveness probe, and the
sys.platform-gated branch in _probe_liveness that dispatches to it.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import types
import unittest
import unittest.mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _bg  # noqa: E402


def _make_fake_ctypes(kernel32):
    """Build fake ctypes/ctypes.wintypes modules wrapping a mocked kernel32.

    _win_pid_alive imports ctypes and ctypes.wintypes inside its own function body, so
    unittest.mock.patch cannot target ctypes.windll.* (there is no module-level ctypes name in _bg
    to patch, and ctypes.windll does not exist at all on this Linux test host). Instead these fake
    modules are installed into sys.modules for the duration of a call, so the function-local import
    statements re-resolve against them.
    """
    fake_windll = types.SimpleNamespace(kernel32=kernel32)
    fake_ctypes = types.ModuleType("ctypes")
    fake_ctypes.windll = fake_windll
    fake_ctypes.byref = lambda x: x  # identity: pass the DWORD object straight through
    fake_wintypes = types.ModuleType("ctypes.wintypes")

    class _FakeDWORD:
        def __init__(self):
            self.value = 0

    fake_wintypes.DWORD = _FakeDWORD
    fake_ctypes.wintypes = fake_wintypes  # set explicitly; do not rely on import-machinery auto-set for a synthetic module
    return fake_ctypes, fake_wintypes


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
                self.assertIn("_probe_liveness", cm.output[0])
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
                self.assertIn("_probe_liveness", cm.output[0])
                self.assertIn("os.kill", cm.output[0])
                self.assertIn("falling back to log-mtime staleness", cm.output[0])

            # Test case (b): stale mtime -> (False, pid)
            with unittest.mock.patch.object(_bg.os, "kill", side_effect=system_error):
                old_ts = time.time() - (_bg._STALE_LOG_SECONDS + 60)
                os.utime(log_path, (old_ts, old_ts))
                alive, pid = _bg.is_bg_worker_alive(log_path)
                self.assertFalse(alive)
                self.assertEqual(pid, pid_value)


class TestWinPidAlive(unittest.TestCase):
    """Test cases for _bg._win_pid_alive, the non-destructive Windows liveness probe."""

    def test_running_process(self) -> None:
        """OpenProcess succeeds, GetExitCodeProcess reports STILL_ACTIVE -> True."""
        kernel32 = unittest.mock.MagicMock()
        kernel32.OpenProcess.return_value = 12345

        def _set_still_active(_hproc, exit_code_ref):
            exit_code_ref.value = 259
            return 1

        kernel32.GetExitCodeProcess.side_effect = _set_still_active
        fake_ctypes, fake_wintypes = _make_fake_ctypes(kernel32)
        with unittest.mock.patch.dict(sys.modules, {"ctypes": fake_ctypes, "ctypes.wintypes": fake_wintypes}):
            result = _bg._win_pid_alive(1234)
        self.assertTrue(result)
        kernel32.CloseHandle.assert_called_once()

    def test_exited_process(self) -> None:
        """OpenProcess succeeds, GetExitCodeProcess reports a non-STILL_ACTIVE code -> False."""
        kernel32 = unittest.mock.MagicMock()
        kernel32.OpenProcess.return_value = 12345

        def _set_exited(_hproc, exit_code_ref):
            exit_code_ref.value = 0
            return 1

        kernel32.GetExitCodeProcess.side_effect = _set_exited
        fake_ctypes, fake_wintypes = _make_fake_ctypes(kernel32)
        with unittest.mock.patch.dict(sys.modules, {"ctypes": fake_ctypes, "ctypes.wintypes": fake_wintypes}):
            result = _bg._win_pid_alive(1234)
        self.assertFalse(result)
        kernel32.CloseHandle.assert_called_once()

    def test_open_process_denied(self) -> None:
        """OpenProcess fails with ERROR_ACCESS_DENIED (5) -> True (process exists, query denied)."""
        kernel32 = unittest.mock.MagicMock()
        kernel32.OpenProcess.return_value = 0
        kernel32.GetLastError.return_value = 5
        fake_ctypes, fake_wintypes = _make_fake_ctypes(kernel32)
        with unittest.mock.patch.dict(sys.modules, {"ctypes": fake_ctypes, "ctypes.wintypes": fake_wintypes}):
            result = _bg._win_pid_alive(1234)
        self.assertTrue(result)
        kernel32.CloseHandle.assert_not_called()

    def test_open_process_invalid_pid(self) -> None:
        """OpenProcess fails with ERROR_INVALID_PARAMETER (87) -> False (no such process)."""
        kernel32 = unittest.mock.MagicMock()
        kernel32.OpenProcess.return_value = 0
        kernel32.GetLastError.return_value = 87
        fake_ctypes, fake_wintypes = _make_fake_ctypes(kernel32)
        with unittest.mock.patch.dict(sys.modules, {"ctypes": fake_ctypes, "ctypes.wintypes": fake_wintypes}):
            result = _bg._win_pid_alive(1234)
        self.assertFalse(result)
        kernel32.CloseHandle.assert_not_called()

    def test_get_exit_code_process_fails(self) -> None:
        """OpenProcess succeeds but GetExitCodeProcess itself fails -> None (inconclusive)."""
        kernel32 = unittest.mock.MagicMock()
        kernel32.OpenProcess.return_value = 12345
        kernel32.GetExitCodeProcess.return_value = 0
        fake_ctypes, fake_wintypes = _make_fake_ctypes(kernel32)
        with unittest.mock.patch.dict(sys.modules, {"ctypes": fake_ctypes, "ctypes.wintypes": fake_wintypes}):
            result = _bg._win_pid_alive(1234)
        self.assertIsNone(result)
        kernel32.CloseHandle.assert_called_once()


class TestProbeLivenessPlatformGate(unittest.TestCase):
    """Test cases for the sys.platform == "win32" branch in _bg._probe_liveness."""

    def _write_log(self, tmp_str: str, pid: int) -> Path:
        log_path = Path(tmp_str) / "test.log"
        log_path.write_text(
            f"[mill-bg] WORKER PID={pid} START 2026-05-17T15:00:00Z\nsome output\n",
            encoding="utf-8",
        )
        return log_path

    def test_windows_affirmative_alive(self) -> None:
        """sys.platform == "win32" and _win_pid_alive returns True -> ("affirmative-alive", pid)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = self._write_log(tmp_str, 1234)
            with unittest.mock.patch.object(_bg.sys, "platform", "win32"), unittest.mock.patch.object(
                _bg, "_win_pid_alive", return_value=True
            ):
                state, pid = _bg._probe_liveness(log_path)
            self.assertEqual(state, "affirmative-alive")
            self.assertEqual(pid, 1234)

    def test_windows_dead(self) -> None:
        """sys.platform == "win32" and _win_pid_alive returns False -> ("dead", pid)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = self._write_log(tmp_str, 1234)
            with unittest.mock.patch.object(_bg.sys, "platform", "win32"), unittest.mock.patch.object(
                _bg, "_win_pid_alive", return_value=False
            ):
                state, pid = _bg._probe_liveness(log_path)
            self.assertEqual(state, "dead")
            self.assertEqual(pid, 1234)

    def test_windows_inconclusive_falls_back_to_fresh_mtime(self) -> None:
        """sys.platform == "win32" and _win_pid_alive returns None, fresh mtime -> ("assumed-alive", pid)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = self._write_log(tmp_str, 1234)
            with unittest.mock.patch.object(_bg.sys, "platform", "win32"), unittest.mock.patch.object(
                _bg, "_win_pid_alive", return_value=None
            ):
                state, pid = _bg._probe_liveness(log_path)
            self.assertEqual(state, "assumed-alive")
            self.assertEqual(pid, 1234)

    def test_windows_inconclusive_falls_back_to_stale_mtime(self) -> None:
        """sys.platform == "win32" and _win_pid_alive returns None, stale mtime -> ("dead", pid)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = self._write_log(tmp_str, 1234)
            old_ts = time.time() - (_bg._STALE_LOG_SECONDS + 60)
            os.utime(log_path, (old_ts, old_ts))
            with unittest.mock.patch.object(_bg.sys, "platform", "win32"), unittest.mock.patch.object(
                _bg, "_win_pid_alive", return_value=None
            ):
                state, pid = _bg._probe_liveness(log_path)
            self.assertEqual(state, "dead")
            self.assertEqual(pid, 1234)

    def test_non_windows_still_uses_os_kill_not_win_pid_alive(self) -> None:
        """sys.platform != "win32" -> os.kill is called and _win_pid_alive is never invoked."""
        with tempfile.TemporaryDirectory() as tmp_str:
            current_pid = os.getpid()
            log_path = self._write_log(tmp_str, current_pid)
            with unittest.mock.patch.object(_bg.sys, "platform", "linux"), unittest.mock.patch.object(
                _bg.os, "kill", wraps=_bg.os.kill
            ) as mock_kill, unittest.mock.patch.object(_bg, "_win_pid_alive") as mock_win_pid_alive:
                state, pid = _bg._probe_liveness(log_path)
            self.assertEqual(state, "affirmative-alive")
            self.assertEqual(pid, current_pid)
            mock_kill.assert_called_once_with(current_pid, 0)
            mock_win_pid_alive.assert_not_called()


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
        """Worker affirmatively alive, no EXIT -> ('running', pid)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            pid_value = os.getpid()
            log_path.write_text(
                f"[mill-bg] WORKER PID={pid_value} START 2026-05-17T15:00:00Z\n"
                "some output\n",
                encoding="utf-8",
            )
            # os.kill will succeed for current process; no mocking needed
            status, code_or_pid = _bg.check_bg_status(log_path)
            self.assertEqual(status, "running")
            self.assertEqual(code_or_pid, pid_value)

    def test_check_bg_status_dead_no_exit(self) -> None:
        """Worker dead (stale mtime), no EXIT -> ('dead', pid)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            pid_value = 99999999
            log_path.write_text(
                f"[mill-bg] WORKER PID={pid_value} START 2026-05-17T15:00:00Z\n"
                "some output\n",
                encoding="utf-8",
            )
            # Backdate mtime so probe reports dead
            old_ts = time.time() - (_bg._STALE_LOG_SECONDS + 60)
            os.utime(log_path, (old_ts, old_ts))
            # Mock os.kill to raise OSError (Windows EINVAL shape)
            with unittest.mock.patch.object(_bg.os, "kill", side_effect=OSError(22, "Invalid parameter")):
                status, code_or_pid = _bg.check_bg_status(log_path)
                self.assertEqual(status, "dead")
                self.assertEqual(code_or_pid, pid_value)

    def test_check_bg_status_race_guard_exit_appears(self) -> None:
        """Probe returns exit sentinel -> ('exit', code) is returned."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            pid_value = 12345
            log_path.write_text(
                f"[mill-bg] WORKER PID={pid_value} START 2026-05-17T15:00:00Z\n"
                "some output\n"
                "[mill-bg] EXIT 42\n",
                encoding="utf-8",
            )
            status, code_or_pid = _bg.check_bg_status(log_path)
            self.assertEqual(status, "exit")
            self.assertEqual(code_or_pid, 42)


    def test_check_bg_status_json_sentinel_completion_with_assumed_alive(self) -> None:
        """Regression test for #420/#424: log with valid trailing JSON + fresh mtime + inconclusive
        kill probe.

        When a worker finishes and emits JSON but is hard-killed before writing EXIT, the probe
        reports assumed-alive (kill inconclusive + fresh mtime), but the JSON sentinel must override
        it to report completion on this poll.
        """
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            pid_value = 99999999
            log_path.write_text(
                f"[mill-bg] WORKER PID={pid_value} START 2026-05-17T15:00:00Z\n"
                "some worker output\n"
                '{"type": "discussion", "round": 1, "verdict": "REQUEST_CHANGES"}\n',
                encoding="utf-8",
            )
            # Fresh mtime + os.kill raises OSError -> probe will report assumed-alive
            with unittest.mock.patch.object(_bg.os, "kill", side_effect=OSError(22, "Invalid parameter")):
                status, code_or_pid = _bg.check_bg_status(log_path)
                self.assertEqual(status, "exit")
                self.assertEqual(code_or_pid, 0)

    def test_check_bg_status_affirmatively_alive_not_false_completed(self) -> None:
        """Affirmatively-alive process with mid-stream JSON is still running."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            pid_value = os.getpid()  # Use current process (alive)
            log_path.write_text(
                f"[mill-bg] WORKER PID={pid_value} START 2026-05-17T15:00:00Z\n"
                '{"partial": "output"}\n'
                "continuing to run\n",
                encoding="utf-8",
            )
            status, code_or_pid = _bg.check_bg_status(log_path)
            self.assertEqual(status, "running")
            self.assertEqual(code_or_pid, pid_value)

    def test_check_bg_status_killed_before_json_fresh_mtime(self) -> None:
        """Dead PID, no EXIT, no JSON, fresh mtime -> ('running', pid)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            pid_value = 99999999
            log_path.write_text(
                f"[mill-bg] WORKER PID={pid_value} START 2026-05-17T15:00:00Z\n"
                "some output\n",
                encoding="utf-8",
            )
            # Fresh mtime + inconclusive kill -> assumed-alive -> running
            with unittest.mock.patch.object(_bg.os, "kill", side_effect=OSError(22, "Invalid parameter")):
                status, code_or_pid = _bg.check_bg_status(log_path)
                self.assertEqual(status, "running")
                self.assertEqual(code_or_pid, pid_value)

    def test_check_bg_status_killed_before_json_stale_mtime(self) -> None:
        """Dead PID, no EXIT, no JSON, stale mtime -> ('dead', pid)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            pid_value = 99999999
            log_path.write_text(
                f"[mill-bg] WORKER PID={pid_value} START 2026-05-17T15:00:00Z\n"
                "some output\n",
                encoding="utf-8",
            )
            # Backdate mtime so probe reports dead
            old_ts = time.time() - (_bg._STALE_LOG_SECONDS + 60)
            os.utime(log_path, (old_ts, old_ts))
            # Inconclusive kill with stale mtime -> dead
            with unittest.mock.patch.object(_bg.os, "kill", side_effect=OSError(22, "Invalid parameter")):
                status, code_or_pid = _bg.check_bg_status(log_path)
                self.assertEqual(status, "dead")
                self.assertEqual(code_or_pid, pid_value)


class TestCheckBgStatusJsonFallback(unittest.TestCase):
    """Test cases for check_bg_status JSON fallback when EXIT marker is missing."""

    def test_dead_no_exit_valid_json_last_line(self) -> None:
        """Dead worker, no EXIT, valid JSON as last line -> ("exit", 0)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            log_path.write_text(
                '[mill-bg] WORKER PID=99999999 START 2026-05-17T15:00:00Z\n'
                'some output\n'
                '{"status":"success","commit_sha":"abc"}\n',
                encoding="utf-8",
            )
            # Backdate mtime so is_bg_worker_alive reports dead
            old_ts = time.time() - (_bg._STALE_LOG_SECONDS + 10)
            os.utime(log_path, (old_ts, old_ts))
            status, code_or_pid = _bg.check_bg_status(log_path)
            self.assertEqual(status, "exit")
            self.assertEqual(code_or_pid, 0)

    def test_dead_no_exit_partial_json_last_line(self) -> None:
        """Dead worker, no EXIT, incomplete JSON last line -> ("dead", pid)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            log_path.write_text(
                '[mill-bg] WORKER PID=99999999 START 2026-05-17T15:00:00Z\n'
                'some output\n'
                '{"status":\n',
                encoding="utf-8",
            )
            # Backdate mtime so is_bg_worker_alive reports dead
            old_ts = time.time() - (_bg._STALE_LOG_SECONDS + 10)
            os.utime(log_path, (old_ts, old_ts))
            status, code_or_pid = _bg.check_bg_status(log_path)
            self.assertEqual(status, "dead")
            self.assertEqual(code_or_pid, 99999999)

    def test_dead_no_exit_no_json(self) -> None:
        """Dead worker, no EXIT, no JSON output -> ("dead", pid)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            log_path.write_text(
                '[mill-bg] WORKER PID=99999999 START 2026-05-17T15:00:00Z\n'
                'some non-JSON output\n'
                'error message\n',
                encoding="utf-8",
            )
            # Backdate mtime so is_bg_worker_alive reports dead
            old_ts = time.time() - (_bg._STALE_LOG_SECONDS + 10)
            os.utime(log_path, (old_ts, old_ts))
            status, code_or_pid = _bg.check_bg_status(log_path)
            self.assertEqual(status, "dead")
            self.assertEqual(code_or_pid, 99999999)

    def test_dead_exit_present_unaffected(self) -> None:
        """EXIT marker present -> ("exit", code) (existing path unaffected)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            log_path.write_text(
                '[mill-bg] WORKER PID=99999999 START 2026-05-17T15:00:00Z\n'
                'some output\n'
                '[mill-bg] EXIT 0\n',
                encoding="utf-8",
            )
            status, code_or_pid = _bg.check_bg_status(log_path)
            self.assertEqual(status, "exit")
            self.assertEqual(code_or_pid, 0)

    def test_dead_no_exit_json_mid_log_only(self) -> None:
        """JSON mid-log but last {-prefixed line is invalid -> ("dead", pid)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            log_path = Path(tmp_str) / "test.log"
            log_path.write_text(
                '[mill-bg] WORKER PID=99999999 START 2026-05-17T15:00:00Z\n'
                '{"valid":"json"}\n'
                'some output\n'
                '{"partial\n',
                encoding="utf-8",
            )
            # Backdate mtime so is_bg_worker_alive reports dead
            old_ts = time.time() - (_bg._STALE_LOG_SECONDS + 10)
            os.utime(log_path, (old_ts, old_ts))
            status, code_or_pid = _bg.check_bg_status(log_path)
            self.assertEqual(status, "dead")
            self.assertEqual(code_or_pid, 99999999)


if __name__ == "__main__":
    unittest.main()
