"""Unit tests for plugins/mill/scripts/_psmux.py.

These tests use unittest.mock.patch against _subprocess_util.run to verify
that each psmux helper constructs the correct argv and timeout. No real psmux
binary is invoked.
"""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import unittest.mock as mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _psmux  # noqa: E402
from _psmux import (  # noqa: E402
    PSMUX_COMMAND_TIMEOUT_S,
    PsmuxError,
    capture_pane,
    kill_session,
    list_sessions,
    load_buffer,
    new_session,
    paste_buffer,
    send_keys,
    set_history_limit,
)


def main() -> int:
    errors = 0

    # Module imports cleanly and public symbols exist
    assert callable(new_session)
    assert callable(set_history_limit)
    assert callable(send_keys)
    assert callable(load_buffer)
    assert callable(paste_buffer)
    assert callable(capture_pane)
    assert callable(kill_session)
    assert callable(list_sessions)
    assert issubclass(PsmuxError, Exception)
    assert PSMUX_COMMAND_TIMEOUT_S == 30
    print("PASS: module imports cleanly, public symbols present")

    # Test new_session
    with mock.patch.object(_psmux._subprocess_util, "run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        new_session("s1", shell_argv=["pwsh", "-NoLogo"])
        call_args = mock_run.call_args
        assert call_args is not None
        argv = call_args[0][0]
        assert argv[:9] == [
            "psmux",
            "new-session",
            "-d",
            "-s",
            "s1",
            "-x",
            "200",
            "-y",
            "50",
        ]
        assert argv[9:] == ["--", "pwsh", "-NoLogo"]
        assert call_args[1]["timeout"] == PSMUX_COMMAND_TIMEOUT_S
    print("PASS: new_session constructs correct argv")

    # Test set_history_limit success
    with mock.patch.object(_psmux._subprocess_util, "run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        set_history_limit("s1", 50000)
        call_args = mock_run.call_args
        assert call_args is not None
        argv = call_args[0][0]
        assert argv == ["psmux", "set-option", "-t", "s1", "-g", "history-limit", "50000"]
    print("PASS: set_history_limit success path constructs correct argv")

    # Test set_history_limit fallback
    with mock.patch.object(_psmux._subprocess_util, "run") as mock_run:
        mock_run.side_effect = PsmuxError("history-limit unsupported")
        stderr_buf = io.StringIO()
        with contextlib.redirect_stderr(stderr_buf):
            set_history_limit("s1", 50000)
        stderr_output = stderr_buf.getvalue()
        assert "[psmux] history-limit unsupported, using default" in stderr_output
    print("PASS: set_history_limit fallback path catches exception and logs")

    # Test send_keys with enter=True
    with mock.patch.object(_psmux._subprocess_util, "run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        send_keys("s1", "claude", enter=True)
        call_args = mock_run.call_args
        assert call_args is not None
        argv = call_args[0][0]
        assert argv == ["psmux", "send-keys", "-t", "s1", "claude", "Enter"]
    print("PASS: send_keys with enter=True constructs correct argv")

    # Test send_keys with enter=False
    with mock.patch.object(_psmux._subprocess_util, "run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        send_keys("s1", "Enter", enter=False)
        call_args = mock_run.call_args
        assert call_args is not None
        argv = call_args[0][0]
        assert argv == ["psmux", "send-keys", "-t", "s1", "Enter"]
    print("PASS: send_keys with enter=False constructs correct argv")

    # Test send_keys with empty keys and enter=False raises ValueError
    try:
        send_keys("s1", "", enter=False)
        assert False, "send_keys should raise ValueError for empty keys"
    except ValueError as e:
        assert "no keys and enter=False" in str(e)
    print("PASS: send_keys raises ValueError for empty keys and enter=False")

    # Test load_buffer
    with mock.patch.object(_psmux._subprocess_util, "run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        load_buffer("s1", "buf1", Path("p.txt"))
        call_args = mock_run.call_args
        assert call_args is not None
        argv = call_args[0][0]
        assert argv == ["psmux", "load-buffer", "-b", "buf1", "p.txt"]
    print("PASS: load_buffer constructs correct argv")

    # Test paste_buffer
    with mock.patch.object(_psmux._subprocess_util, "run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        paste_buffer("s1", "buf1")
        call_args = mock_run.call_args
        assert call_args is not None
        argv = call_args[0][0]
        assert argv == ["psmux", "paste-buffer", "-t", "s1", "-b", "buf1"]
    print("PASS: paste_buffer constructs correct argv")

    # Test capture_pane
    with mock.patch.object(_psmux._subprocess_util, "run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, stdout="hello", stderr=""
        )
        result = capture_pane("s1")
        assert result == "hello"
        call_args = mock_run.call_args
        assert call_args is not None
        argv = call_args[0][0]
        assert argv == ["psmux", "capture-pane", "-t", "s1", "-S", "-50000", "-p"]
    print("PASS: capture_pane returns stdout and constructs correct argv")

    # Test kill_session success
    with mock.patch.object(_psmux._subprocess_util, "run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        kill_session("s1")
        call_args = mock_run.call_args
        assert call_args is not None
        argv = call_args[0][0]
        assert argv == ["psmux", "kill-session", "-t", "s1"]
    print("PASS: kill_session success path constructs correct argv")

    # Test kill_session with "no such session" error
    with mock.patch.object(_psmux._subprocess_util, "run") as mock_run:
        mock_run.side_effect = PsmuxError("no such session")
        kill_session("s1")
    print("PASS: kill_session swallows 'no such session' errors")

    # Test list_sessions with normal output
    with mock.patch.object(_psmux._subprocess_util, "run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, stdout="alpha: x\nbeta: y\n", stderr=""
        )
        result = list_sessions()
        assert result == ["alpha", "beta"]
    print("PASS: list_sessions parses stdout correctly")

    # Test list_sessions with empty output
    with mock.patch.object(_psmux._subprocess_util, "run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        result = list_sessions()
        assert result == []
    print("PASS: list_sessions returns empty list for empty stdout")

    # Test list_sessions with "no server running" error
    with mock.patch.object(_psmux._subprocess_util, "run") as mock_run:
        mock_run.side_effect = PsmuxError("no server running")
        result = list_sessions()
        assert result == []
    print("PASS: list_sessions returns empty list for 'no server running' error")

    return errors


if __name__ == "__main__":
    sys.exit(main())
