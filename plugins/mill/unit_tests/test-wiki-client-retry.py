"""Unit tests for wiki client transient-error retry logic in _dispatch.

Covers: ConnectionResetError, ConnectionRefusedError, TimeoutError retries
in _dispatch; non-retryable errors pass through; persistent failures raise
WikiBusyError.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from wiki import (
    WikiBusyError,
)  # noqa: E402
from wiki import _client  # noqa: E402
from _test_helpers import safe_temp_dir  # noqa: E402


def main() -> int:
    passed = 0
    failed = 0

    def ok(name: str) -> None:
        nonlocal passed
        passed += 1
        print(f"PASS: {name}")

    def fail(name: str, exc: Exception) -> None:
        nonlocal failed
        failed += 1
        print(f"FAIL: {name}: {exc}", file=sys.stderr)

    # --- (1) ConnectionResetError raised once then success ---
    try:
        with safe_temp_dir() as tmp:
            wiki_path = tmp / "wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)

            call_count = 0
            def mock_connect_send_recv(host, port, msg, *, timeout=10.0):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ConnectionResetError("connection reset")
                return {"ok": True}

            sleep_calls = []
            def mock_sleep(seconds):
                sleep_calls.append(seconds)

            with patch.dict(os.environ, {"WIKI_DAEMON_INPROCESS": ""}), \
                 patch.object(_client, "_connect_send_recv", mock_connect_send_recv), \
                 patch("time.sleep", mock_sleep), \
                 patch.object(_client, "_ensure_daemon", return_value=("127.0.0.1", 9999, "token")):
                resp = _client._dispatch(wiki_path, "test_op", {})
                assert resp == {"ok": True}, f"expected {{'ok': True}}, got {resp}"
                assert call_count == 2, f"expected 2 calls, got {call_count}"
                assert len(sleep_calls) == 1, f"expected 1 sleep call, got {len(sleep_calls)}"
                assert sleep_calls[0] == 2, f"expected sleep(2), got sleep({sleep_calls[0]})"
                ok("ConnectionResetError raised once then success")
    except Exception as exc:
        fail("ConnectionResetError raised once then success", exc)

    # --- (2) ConnectionRefusedError raised once then success ---
    try:
        with safe_temp_dir() as tmp:
            wiki_path = tmp / "wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)

            call_count = 0
            def mock_connect_send_recv(host, port, msg, *, timeout=10.0):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ConnectionRefusedError("connection refused")
                return {"ok": True}

            sleep_calls = []
            def mock_sleep(seconds):
                sleep_calls.append(seconds)

            with patch.dict(os.environ, {"WIKI_DAEMON_INPROCESS": ""}), \
                 patch.object(_client, "_connect_send_recv", mock_connect_send_recv), \
                 patch("time.sleep", mock_sleep), \
                 patch.object(_client, "_ensure_daemon", return_value=("127.0.0.1", 9999, "token")):
                resp = _client._dispatch(wiki_path, "test_op", {})
                assert resp == {"ok": True}, f"expected {{'ok': True}}, got {resp}"
                assert call_count == 2, f"expected 2 calls, got {call_count}"
                assert len(sleep_calls) == 1, f"expected 1 sleep call, got {len(sleep_calls)}"
                ok("ConnectionRefusedError raised once then success")
    except Exception as exc:
        fail("ConnectionRefusedError raised once then success", exc)

    # --- (3) Persistent ConnectionRefusedError across all attempts ---
    try:
        with safe_temp_dir() as tmp:
            wiki_path = tmp / "wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)

            call_count = 0
            def mock_connect_send_recv(host, port, msg, *, timeout=10.0):
                nonlocal call_count
                call_count += 1
                raise ConnectionRefusedError("connection refused")

            sleep_calls = []
            def mock_sleep(seconds):
                sleep_calls.append(seconds)

            with patch.dict(os.environ, {"WIKI_DAEMON_INPROCESS": ""}), \
                 patch.object(_client, "_connect_send_recv", mock_connect_send_recv), \
                 patch("time.sleep", mock_sleep), \
                 patch.object(_client, "_ensure_daemon", return_value=("127.0.0.1", 9999, "token")):
                try:
                    _client._dispatch(wiki_path, "test_op", {})
                    fail("Persistent ConnectionRefusedError across all attempts",
                         Exception("expected WikiBusyError"))
                except WikiBusyError as e:
                    assert "daemon stayed busy" in str(e), f"error message should mention 'daemon stayed busy', got {str(e)}"
                    assert "test_op" in str(e), f"error message should mention operation name 'test_op', got {str(e)}"
                    assert call_count == 4, f"expected 4 attempts, got {call_count}"
                    assert len(sleep_calls) == 3, f"expected 3 sleep calls, got {len(sleep_calls)}"
                    ok("Persistent ConnectionRefusedError across all attempts")
    except Exception as exc:
        fail("Persistent ConnectionRefusedError across all attempts", exc)

    # --- (4) TimeoutError raised once then success ---
    try:
        with safe_temp_dir() as tmp:
            wiki_path = tmp / "wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)

            call_count = 0
            def mock_connect_send_recv(host, port, msg, *, timeout=10.0):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise TimeoutError("timeout")
                return {"ok": True}

            sleep_calls = []
            def mock_sleep(seconds):
                sleep_calls.append(seconds)

            with patch.dict(os.environ, {"WIKI_DAEMON_INPROCESS": ""}), \
                 patch.object(_client, "_connect_send_recv", mock_connect_send_recv), \
                 patch("time.sleep", mock_sleep), \
                 patch.object(_client, "_ensure_daemon", return_value=("127.0.0.1", 9999, "token")):
                resp = _client._dispatch(wiki_path, "test_op", {})
                assert resp == {"ok": True}, f"expected {{'ok': True}}, got {resp}"
                assert call_count == 2, f"expected 2 calls, got {call_count}"
                ok("TimeoutError raised once then success")
    except Exception as exc:
        fail("TimeoutError raised once then success", exc)

    # --- (5) Non-retryable error (ValueError) propagates without retry ---
    try:
        with safe_temp_dir() as tmp:
            wiki_path = tmp / "wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)

            call_count = 0
            def mock_connect_send_recv(host, port, msg, *, timeout=10.0):
                nonlocal call_count
                call_count += 1
                raise ValueError("bad value")

            sleep_calls = []
            def mock_sleep(seconds):
                sleep_calls.append(seconds)

            with patch.dict(os.environ, {"WIKI_DAEMON_INPROCESS": ""}), \
                 patch.object(_client, "_connect_send_recv", mock_connect_send_recv), \
                 patch("time.sleep", mock_sleep), \
                 patch.object(_client, "_ensure_daemon", return_value=("127.0.0.1", 9999, "token")):
                try:
                    _client._dispatch(wiki_path, "test_op", {})
                    fail("Non-retryable error (ValueError) propagates without retry",
                         Exception("expected ValueError"))
                except ValueError as e:
                    assert str(e) == "bad value", f"error message should be 'bad value', got {str(e)}"
                    assert call_count == 1, f"expected 1 call (no retry), got {call_count}"
                    assert len(sleep_calls) == 0, f"expected 0 sleep calls, got {len(sleep_calls)}"
                    ok("Non-retryable error (ValueError) propagates without retry")
    except Exception as exc:
        fail("Non-retryable error (ValueError) propagates without retry", exc)

    # --- (6) Backoff schedule is [2, 4, 8] ---
    try:
        with safe_temp_dir() as tmp:
            wiki_path = tmp / "wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)

            call_count = 0
            def mock_connect_send_recv(host, port, msg, *, timeout=10.0):
                nonlocal call_count
                call_count += 1
                raise TimeoutError("timeout")

            sleep_calls = []
            def mock_sleep(seconds):
                sleep_calls.append(seconds)

            with patch.dict(os.environ, {"WIKI_DAEMON_INPROCESS": ""}), \
                 patch.object(_client, "_connect_send_recv", mock_connect_send_recv), \
                 patch("time.sleep", mock_sleep), \
                 patch.object(_client, "_ensure_daemon", return_value=("127.0.0.1", 9999, "token")):
                try:
                    _client._dispatch(wiki_path, "test_op", {})
                except WikiBusyError:
                    pass
                assert sleep_calls == [2, 4, 8], f"expected [2, 4, 8], got {sleep_calls}"
                ok("Backoff schedule is [2, 4, 8]")
    except Exception as exc:
        fail("Backoff schedule is [2, 4, 8]", exc)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
