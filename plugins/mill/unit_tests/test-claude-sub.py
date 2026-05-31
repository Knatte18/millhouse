"""Unit tests for plugins/mill/scripts/millpy-claude-sub.py.

Tests exercise the keepalive and reuse logic added in batch 2:
- Flag plumbing (--psmux-session, --keep-alive)
- Reuse short-circuit when named session exists and is idle
- Cleanup ownership rules (success kill gated by --keep-alive, error kill gated by session_owned_by_us)
- Config plumbing for reuse_idle_timeout_s
"""
from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest.mock as mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

_CLAUDE_SUB_PY = HUB / "plugins" / "mill" / "scripts" / "millpy-claude-sub.py"


def _load_claude_sub_module():
    """Load millpy-claude-sub as a module (filename has hyphen)."""
    spec = importlib.util.spec_from_file_location("millpy_claude_sub", str(_CLAUDE_SUB_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    """Run all test cases S1-S11 plus _wait_for_idle_stable unit tests."""
    errors = 0

    # ── S1: existing-idle short-circuit ──────────────────────────────────────
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            mod = _load_claude_sub_module()
            tmpdir_path = Path(tmpdir)

            def mock_list_sessions():
                return ["existing-idle"]

            def mock_wait_for_idle(session_name, timeout_s):
                return True

            def mock_capture_pane(session_name, **kwargs):
                return "  ❯ \n● ok\n  ❯ "

            def mock_extract_response(snapshot):
                return "ok"

            saved_argv = sys.argv[:]
            saved_stdin = sys.stdin
            try:
                sys.argv = [
                    str(_CLAUDE_SUB_PY),
                    "--mode", "bulk",
                    "--model", "claude-opus",
                    "--psmux-session", "existing-idle",
                ]
                sys.stdin = io.StringIO("test prompt")

                with mock.patch("_psmux.new_session") as m_new_session, \
                     mock.patch("_psmux.set_history_limit"), \
                     mock.patch("_psmux.list_sessions", side_effect=mock_list_sessions), \
                     mock.patch("_psmux.send_keys") as m_send_keys, \
                     mock.patch("_psmux.load_buffer"), \
                     mock.patch("_psmux.paste_buffer"), \
                     mock.patch("_psmux.capture_pane", side_effect=mock_capture_pane), \
                     mock.patch("_psmux.kill_session"), \
                     mock.patch("_psmux_capture.extract_response", side_effect=mock_extract_response), \
                     mock.patch.object(mod, "_wait_for_marker_in_pane", return_value=True), \
                     mock.patch.object(mod, "_wait_for_idle_prompt", side_effect=mock_wait_for_idle), \
                     mock.patch.object(mod, "_wait_for_idle_stable", return_value=True), \
                     mock.patch("_paths.resolve_git_root", return_value=tmpdir_path), \
                     mock.patch("_config.load_config", return_value={}), \
                     mock.patch("sys.stdout", new_callable=io.StringIO):

                    ret = mod.main()

                    # Should not call new_session on reuse path
                    assert m_new_session.call_count == 0, "new_session should not be called on reuse"
                    # Should return 0 on success
                    assert ret == 0, f"S1: expected 0, got {ret}"
                    # Should call send_keys 4 times: Escape (reuse clear), then Step 10 bracketed paste (3 calls) + Enter
                    assert m_send_keys.call_count == 4, \
                        f"send_keys should be called 4 times (Escape + bracketed paste + Enter), got {m_send_keys.call_count}"
                    # Verify the first call is Escape
                    assert m_send_keys.call_args_list[0][0][1] == "Escape", \
                        f"send_keys first call should be 'Escape', got {m_send_keys.call_args_list[0][0][1]}"
                    assert m_send_keys.call_args_list[0][1].get("enter") is False, \
                        f"send_keys first call should have enter=False, got {m_send_keys.call_args_list[0][1]}"
                    # Verify the last call is the Enter key
                    assert m_send_keys.call_args[0][1] == "Enter", \
                        f"send_keys last call should be with 'Enter', got {m_send_keys.call_args[0][1]}"
                    print("PASS: S1 (existing-idle short-circuit)")
            finally:
                sys.argv = saved_argv
                sys.stdin = saved_stdin
    except Exception as e:
        print(f"FAIL: S1 - {e}")
        errors += 1

    # ── S2: existing-busy raise ─────────────────────────────────────────────
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            mod = _load_claude_sub_module()
            tmpdir_path = Path(tmpdir)

            def mock_list_sessions():
                return ["existing-busy"]

            def mock_wait_for_idle_fails(session_name, timeout_s):
                return False

            saved_argv = sys.argv[:]
            saved_stdin = sys.stdin
            stderr_capture = io.StringIO()
            try:
                sys.argv = [
                    str(_CLAUDE_SUB_PY),
                    "--mode", "bulk",
                    "--model", "claude-opus",
                    "--psmux-session", "existing-busy",
                ]
                sys.stdin = io.StringIO("test prompt")

                with mock.patch("_psmux.list_sessions", side_effect=mock_list_sessions), \
                     mock.patch.object(mod, "_wait_for_idle_prompt", side_effect=mock_wait_for_idle_fails), \
                     mock.patch("_paths.resolve_git_root", return_value=tmpdir_path), \
                     mock.patch("_config.load_config", return_value={}), \
                     mock.patch("sys.stdout", new_callable=io.StringIO), \
                     mock.patch("sys.stderr", stderr_capture):

                    ret = mod.main()

                    assert ret == 1, f"S2: expected 1, got {ret}"
                    stderr_text = stderr_capture.getvalue()
                    assert "cannot reuse psmux session existing-busy: not idle" in stderr_text, \
                        f"S2: expected error message not in stderr: {stderr_text}"
                    print("PASS: S2 (existing-busy raise)")
            finally:
                sys.argv = saved_argv
                sys.stdin = saved_stdin
    except Exception as e:
        print(f"FAIL: S2 - {e}")
        errors += 1

    # ── S3: reused session not killed on failure ────────────────────────────
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            mod = _load_claude_sub_module()
            tmpdir_path = Path(tmpdir)

            def mock_list_sessions():
                return ["existing-busy"]

            def mock_wait_for_idle_fails(session_name, timeout_s):
                return False

            saved_argv = sys.argv[:]
            saved_stdin = sys.stdin
            try:
                sys.argv = [
                    str(_CLAUDE_SUB_PY),
                    "--mode", "bulk",
                    "--model", "claude-opus",
                    "--psmux-session", "existing-busy",
                ]
                sys.stdin = io.StringIO("test prompt")

                with mock.patch("_psmux.list_sessions", side_effect=mock_list_sessions), \
                     mock.patch.object(mod, "_wait_for_idle_prompt", side_effect=mock_wait_for_idle_fails), \
                     mock.patch("_psmux.kill_session") as m_kill, \
                     mock.patch("_paths.resolve_git_root", return_value=tmpdir_path), \
                     mock.patch("_config.load_config", return_value={}), \
                     mock.patch("sys.stdout", new_callable=io.StringIO), \
                     mock.patch("sys.stderr", new_callable=io.StringIO):

                    ret = mod.main()

                    # Kill should not be called (reused session not owned by us)
                    assert m_kill.call_count == 0, "kill_session should not be called for reused session on failure"
                    print("PASS: S3 (reused session not killed on failure)")
            finally:
                sys.argv = saved_argv
                sys.stdin = saved_stdin
    except Exception as e:
        print(f"FAIL: S3 - {e}")
        errors += 1

    # ── S4: keep-alive true, success path ───────────────────────────────────
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            mod = _load_claude_sub_module()
            tmpdir_path = Path(tmpdir)
            scratch_dir = tmpdir_path / ".scratch"
            scratch_dir.mkdir(exist_ok=True)

            def mock_list_sessions():
                return []

            def mock_capture_pane(session_name, **kwargs):
                return "  ❯ \n● ok\n  ❯ "

            def mock_extract_response(snapshot):
                return "ok"

            saved_argv = sys.argv[:]
            saved_stdin = sys.stdin
            try:
                sys.argv = [
                    str(_CLAUDE_SUB_PY),
                    "--mode", "bulk",
                    "--model", "claude-opus",
                    "--psmux-session", "new-name",
                    "--keep-alive",
                ]
                sys.stdin = io.StringIO("test prompt")

                with mock.patch("_psmux.new_session"), \
                     mock.patch("_psmux.set_history_limit"), \
                     mock.patch("_psmux.list_sessions", side_effect=mock_list_sessions), \
                     mock.patch("_psmux.send_keys"), \
                     mock.patch("_psmux.load_buffer"), \
                     mock.patch("_psmux.paste_buffer"), \
                     mock.patch("_psmux.capture_pane", side_effect=mock_capture_pane), \
                     mock.patch("_psmux.kill_session") as m_kill, \
                     mock.patch("_psmux_capture.extract_response", side_effect=mock_extract_response), \
                     mock.patch.object(mod, "_wait_for_marker_in_pane", return_value=True), \
                     mock.patch.object(mod, "_wait_for_idle_prompt", return_value=True), \
                     mock.patch.object(mod, "_wait_for_idle_stable", return_value=True), \
                     mock.patch("_paths.resolve_git_root", return_value=tmpdir_path), \
                     mock.patch("_config.load_config", return_value={}), \
                     mock.patch("sys.stdout", new_callable=io.StringIO):

                    ret = mod.main()

                    # Kill should not be called (keep-alive flag is set)
                    assert m_kill.call_count == 0, "kill_session should not be called with --keep-alive"
                    assert ret == 0, f"S4: expected 0, got {ret}"
                    print("PASS: S4 (keep-alive true, success path)")
            finally:
                sys.argv = saved_argv
                sys.stdin = saved_stdin
    except Exception as e:
        print(f"FAIL: S4 - {e}")
        errors += 1

    # ── S5: keep-alive true, error mid-call when wrapper owns session ────────
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            mod = _load_claude_sub_module()
            tmpdir_path = Path(tmpdir)
            scratch_dir = tmpdir_path / ".scratch"
            scratch_dir.mkdir(exist_ok=True)

            def mock_list_sessions():
                return []

            def mock_wait_for_idle_fails(session_name, timeout_s):
                return False

            saved_argv = sys.argv[:]
            saved_stdin = sys.stdin
            try:
                sys.argv = [
                    str(_CLAUDE_SUB_PY),
                    "--mode", "bulk",
                    "--model", "claude-opus",
                    "--psmux-session", "new-name",
                    "--keep-alive",
                ]
                sys.stdin = io.StringIO("test prompt")

                with mock.patch("_psmux.new_session"), \
                     mock.patch("_psmux.set_history_limit"), \
                     mock.patch("_psmux.list_sessions", side_effect=mock_list_sessions), \
                     mock.patch("_psmux.send_keys"), \
                     mock.patch("_psmux.capture_pane", return_value=""), \
                     mock.patch("_psmux.kill_session") as m_kill, \
                     mock.patch.object(mod, "_wait_for_marker_in_pane", return_value=True), \
                     mock.patch.object(mod, "_wait_for_idle_prompt", side_effect=mock_wait_for_idle_fails), \
                     mock.patch("_paths.resolve_git_root", return_value=tmpdir_path), \
                     mock.patch("_config.load_config", return_value={}), \
                     mock.patch("sys.stdout", new_callable=io.StringIO), \
                     mock.patch("sys.stderr", new_callable=io.StringIO):

                    ret = mod.main()

                    # Kill should be called (we own the session, and it's the error path)
                    assert m_kill.call_count > 0, "kill_session should be called on error when wrapper owns session"
                    assert ret == 1, f"S5: expected 1, got {ret}"
                    print("PASS: S5 (keep-alive true, error mid-call when wrapper owns session)")
            finally:
                sys.argv = saved_argv
                sys.stdin = saved_stdin
    except Exception as e:
        print(f"FAIL: S5 - {e}")
        errors += 1

    # ── S6: regression guard, no flags ──────────────────────────────────────
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            mod = _load_claude_sub_module()
            tmpdir_path = Path(tmpdir)
            scratch_dir = tmpdir_path / ".scratch"
            scratch_dir.mkdir(exist_ok=True)

            def mock_capture_pane(session_name, **kwargs):
                return "  ❯ \n● Hello\n  ❯ "

            def mock_extract_response(snapshot):
                return "ok"

            saved_argv = sys.argv[:]
            saved_stdin = sys.stdin
            try:
                sys.argv = [
                    str(_CLAUDE_SUB_PY),
                    "--mode", "bulk",
                    "--model", "claude-opus",
                ]
                sys.stdin = io.StringIO("test prompt")

                with mock.patch("_psmux.new_session"), \
                     mock.patch("_psmux.set_history_limit"), \
                     mock.patch("_psmux.send_keys"), \
                     mock.patch("_psmux.load_buffer"), \
                     mock.patch("_psmux.paste_buffer"), \
                     mock.patch("_psmux.capture_pane", side_effect=mock_capture_pane), \
                     mock.patch("_psmux.kill_session") as m_kill, \
                     mock.patch("_psmux_capture.extract_response", side_effect=mock_extract_response), \
                     mock.patch.object(mod, "_wait_for_marker_in_pane", return_value=True), \
                     mock.patch.object(mod, "_wait_for_idle_prompt", return_value=True), \
                     mock.patch.object(mod, "_wait_for_idle_stable", return_value=True), \
                     mock.patch("_paths.resolve_git_root", return_value=tmpdir_path), \
                     mock.patch("_config.load_config", return_value={}), \
                     mock.patch("sys.stdout", new_callable=io.StringIO):

                    ret = mod.main()

                    # Kill should be called (auto-generated session, success path without --keep-alive)
                    assert m_kill.call_count > 0, "kill_session should be called for auto-gen session on success"
                    assert ret == 0, f"S6: expected 0, got {ret}"
                    print("PASS: S6 (regression guard, no flags)")
            finally:
                sys.argv = saved_argv
                sys.stdin = saved_stdin
    except Exception as e:
        print(f"FAIL: S6 - {e}")
        errors += 1

    # ── S7: named-but-missing creates with chosen name ──────────────────────
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            mod = _load_claude_sub_module()
            tmpdir_path = Path(tmpdir)
            scratch_dir = tmpdir_path / ".scratch"
            scratch_dir.mkdir(exist_ok=True)

            def mock_list_sessions():
                return []

            def mock_capture_pane(session_name, **kwargs):
                return "  ❯ \n● ok\n  ❯ "

            def mock_extract_response(snapshot):
                return "ok"

            saved_argv = sys.argv[:]
            saved_stdin = sys.stdin
            try:
                sys.argv = [
                    str(_CLAUDE_SUB_PY),
                    "--mode", "bulk",
                    "--model", "claude-opus",
                    "--psmux-session", "new-name",
                ]
                sys.stdin = io.StringIO("test prompt")

                with mock.patch("_psmux.new_session") as m_new_session, \
                     mock.patch("_psmux.set_history_limit"), \
                     mock.patch("_psmux.list_sessions", side_effect=mock_list_sessions), \
                     mock.patch("_psmux.send_keys"), \
                     mock.patch("_psmux.load_buffer"), \
                     mock.patch("_psmux.paste_buffer"), \
                     mock.patch("_psmux.capture_pane", side_effect=mock_capture_pane), \
                     mock.patch("_psmux.kill_session"), \
                     mock.patch("_psmux_capture.extract_response", side_effect=mock_extract_response), \
                     mock.patch.object(mod, "_wait_for_marker_in_pane", return_value=True), \
                     mock.patch.object(mod, "_wait_for_idle_prompt", return_value=True), \
                     mock.patch.object(mod, "_wait_for_idle_stable", return_value=True), \
                     mock.patch("_paths.resolve_git_root", return_value=tmpdir_path), \
                     mock.patch("_config.load_config", return_value={}), \
                     mock.patch("sys.stdout", new_callable=io.StringIO):

                    ret = mod.main()

                    # Check that new_session was called with the chosen name
                    m_new_session.assert_called_once()
                    assert m_new_session.call_args[0][0] == "new-name", \
                        f"new_session should be called with 'new-name' as positional arg, got {m_new_session.call_args[0][0]}"
                    call_kwargs = m_new_session.call_args[1]
                    assert call_kwargs.get("shell_argv") is not None, "shell_argv not provided to new_session"
                    print("PASS: S7 (named-but-missing creates with chosen name)")
            finally:
                sys.argv = saved_argv
                sys.stdin = saved_stdin
    except Exception as e:
        print(f"FAIL: S7 - {e}")
        errors += 1

    # ── S8: list_sessions raises PsmuxError ─────────────────────────────────
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            mod = _load_claude_sub_module()
            tmpdir_path = Path(tmpdir)

            def mock_list_sessions_raises():
                raise mod._psmux.PsmuxError("psmux broken")

            saved_argv = sys.argv[:]
            saved_stdin = sys.stdin
            stderr_capture = io.StringIO()
            try:
                sys.argv = [
                    str(_CLAUDE_SUB_PY),
                    "--mode", "bulk",
                    "--model", "claude-opus",
                    "--psmux-session", "any-name",
                ]
                sys.stdin = io.StringIO("test prompt")

                with mock.patch("_psmux.new_session") as m_new_session, \
                     mock.patch("_psmux.list_sessions", side_effect=mock_list_sessions_raises), \
                     mock.patch("_paths.resolve_git_root", return_value=tmpdir_path), \
                     mock.patch("_config.load_config", return_value={}), \
                     mock.patch("sys.stdout", new_callable=io.StringIO), \
                     mock.patch("sys.stderr", stderr_capture):

                    ret = mod.main()

                    # Should not call new_session when list_sessions raises
                    assert m_new_session.call_count == 0, "new_session should not be called when list_sessions raises"
                    assert ret == 1, f"S8: expected 1, got {ret}"
                    stderr_text = stderr_capture.getvalue()
                    assert "psmux broken" in stderr_text, f"S8: expected error message not in stderr: {stderr_text}"
                    print("PASS: S8 (list_sessions raises PsmuxError)")
            finally:
                sys.argv = saved_argv
                sys.stdin = saved_stdin
    except Exception as e:
        print(f"FAIL: S8 - {e}")
        errors += 1

    # ── S9: reuse_idle_timeout_s is plumbed from config ─────────────────────
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            def mock_list_sessions():
                return ["existing-idle"]

            # Capture the timeout passed to _wait_for_idle_prompt
            captured_timeout = []

            def mock_wait_for_idle_with_capture(session_name, timeout_s):
                captured_timeout.append(timeout_s)
                return True

            def mock_capture_pane(session_name, **kwargs):
                return "  ❯ \n● ok\n  ❯ "

            def mock_extract_response(snapshot):
                return "ok"

            # Test 1: with config value = 42
            mod1 = _load_claude_sub_module()
            saved_argv = sys.argv[:]
            saved_stdin = sys.stdin
            try:
                sys.argv = [
                    str(_CLAUDE_SUB_PY),
                    "--mode", "bulk",
                    "--model", "claude-opus",
                    "--psmux-session", "existing-idle",
                ]
                sys.stdin = io.StringIO("test prompt")

                with mock.patch("_psmux.new_session"), \
                     mock.patch("_psmux.set_history_limit"), \
                     mock.patch("_psmux.list_sessions", side_effect=mock_list_sessions), \
                     mock.patch("_psmux.send_keys"), \
                     mock.patch("_psmux.load_buffer"), \
                     mock.patch("_psmux.paste_buffer"), \
                     mock.patch("_psmux.capture_pane", side_effect=mock_capture_pane), \
                     mock.patch("_psmux.kill_session"), \
                     mock.patch("_psmux_capture.extract_response", side_effect=mock_extract_response), \
                     mock.patch.object(mod1, "_wait_for_marker_in_pane", return_value=True), \
                     mock.patch.object(mod1, "_wait_for_idle_prompt", side_effect=mock_wait_for_idle_with_capture), \
                     mock.patch.object(mod1, "_wait_for_idle_stable", return_value=True), \
                     mock.patch("_paths.resolve_git_root", return_value=tmpdir_path), \
                     mock.patch("_config.load_config", return_value={"llm": {"claude": {"psmux": {"reuse_idle_timeout_s": 42}}}}), \
                     mock.patch("sys.stdout", new_callable=io.StringIO):

                    captured_timeout.clear()
                    ret = mod1.main()
                    assert ret == 0, f"S9 test 1 failed: expected 0, got {ret}"
                    assert len(captured_timeout) > 0, "timeout not captured in test 1"
                    assert captured_timeout[0] == 42.0, f"Expected 42.0, got {captured_timeout[0]}"
            finally:
                sys.argv = saved_argv
                sys.stdin = saved_stdin

            # Test 2: without config value (should use default)
            mod2 = _load_claude_sub_module()
            saved_argv = sys.argv[:]
            saved_stdin = sys.stdin
            try:
                sys.argv = [
                    str(_CLAUDE_SUB_PY),
                    "--mode", "bulk",
                    "--model", "claude-opus",
                    "--psmux-session", "existing-idle",
                ]
                sys.stdin = io.StringIO("test prompt")

                with mock.patch("_psmux.new_session"), \
                     mock.patch("_psmux.set_history_limit"), \
                     mock.patch("_psmux.list_sessions", side_effect=mock_list_sessions), \
                     mock.patch("_psmux.send_keys"), \
                     mock.patch("_psmux.load_buffer"), \
                     mock.patch("_psmux.paste_buffer"), \
                     mock.patch("_psmux.capture_pane", side_effect=mock_capture_pane), \
                     mock.patch("_psmux.kill_session"), \
                     mock.patch("_psmux_capture.extract_response", side_effect=mock_extract_response), \
                     mock.patch.object(mod2, "_wait_for_marker_in_pane", return_value=True), \
                     mock.patch.object(mod2, "_wait_for_idle_prompt", side_effect=mock_wait_for_idle_with_capture), \
                     mock.patch.object(mod2, "_wait_for_idle_stable", return_value=True), \
                     mock.patch("_paths.resolve_git_root", return_value=tmpdir_path), \
                     mock.patch("_config.load_config", return_value={}), \
                     mock.patch("sys.stdout", new_callable=io.StringIO):

                    captured_timeout.clear()
                    ret = mod2.main()
                    assert ret == 0, f"S9 test 2 failed: expected 0, got {ret}"
                    assert len(captured_timeout) > 0, "timeout not captured in test 2"
                    assert captured_timeout[0] == 10.0, f"Expected 10.0 (default), got {captured_timeout[0]}"
            finally:
                sys.argv = saved_argv
                sys.stdin = saved_stdin

            print("PASS: S9 (reuse_idle_timeout_s is plumbed from config)")
    except Exception as e:
        print(f"FAIL: S9 - {e}")
        errors += 1

    # ── S10: _wait_for_idle_stable timeout ──────────────────────────────────
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            mod = _load_claude_sub_module()
            tmpdir_path = Path(tmpdir)
            scratch_dir = tmpdir_path / ".scratch"
            scratch_dir.mkdir(exist_ok=True)

            def mock_list_sessions():
                return []

            saved_argv = sys.argv[:]
            saved_stdin = sys.stdin
            stderr_capture = io.StringIO()
            try:
                sys.argv = [
                    str(_CLAUDE_SUB_PY),
                    "--mode", "bulk",
                    "--model", "claude-opus",
                ]
                sys.stdin = io.StringIO("test prompt")

                with mock.patch("_psmux.new_session"), \
                     mock.patch("_psmux.set_history_limit"), \
                     mock.patch("_psmux.list_sessions", side_effect=mock_list_sessions), \
                     mock.patch("_psmux.send_keys"), \
                     mock.patch("_psmux.load_buffer"), \
                     mock.patch("_psmux.paste_buffer"), \
                     mock.patch("_psmux.capture_pane", return_value=""), \
                     mock.patch("_psmux.kill_session") as m_kill, \
                     mock.patch.object(mod, "_wait_for_marker_in_pane", return_value=True), \
                     mock.patch.object(mod, "_wait_for_idle_prompt", return_value=True), \
                     mock.patch.object(mod, "_wait_for_idle_stable", return_value=False), \
                     mock.patch("_paths.resolve_git_root", return_value=tmpdir_path), \
                     mock.patch("_config.load_config", return_value={}), \
                     mock.patch("sys.stdout", new_callable=io.StringIO), \
                     mock.patch("sys.stderr", stderr_capture):

                    ret = mod.main()

                    assert ret == 1, f"S10: expected 1, got {ret}"
                    assert m_kill.call_count > 0, "kill_session should be called on error when wrapper owns session"
                    stderr_text = stderr_capture.getvalue()
                    assert "response-poll timeout" in stderr_text, \
                        f"S10: expected 'response-poll timeout' in stderr: {stderr_text}"
                    print("PASS: S10 (_wait_for_idle_stable timeout)")
            finally:
                sys.argv = saved_argv
                sys.stdin = saved_stdin
    except Exception as e:
        print(f"FAIL: S10 - {e}")
        errors += 1

    # ── S11: extract_response raises MarkerNotFoundError ─────────────────────
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            import _psmux_capture as _psmux_capture_mod
            mod = _load_claude_sub_module()
            tmpdir_path = Path(tmpdir)
            scratch_dir = tmpdir_path / ".scratch"
            scratch_dir.mkdir(exist_ok=True)

            def mock_list_sessions():
                return []

            saved_argv = sys.argv[:]
            saved_stdin = sys.stdin
            stderr_capture = io.StringIO()
            try:
                sys.argv = [
                    str(_CLAUDE_SUB_PY),
                    "--mode", "bulk",
                    "--model", "claude-opus",
                ]
                sys.stdin = io.StringIO("test prompt")

                with mock.patch("_psmux.new_session"), \
                     mock.patch("_psmux.set_history_limit"), \
                     mock.patch("_psmux.list_sessions", side_effect=mock_list_sessions), \
                     mock.patch("_psmux.send_keys"), \
                     mock.patch("_psmux.load_buffer"), \
                     mock.patch("_psmux.paste_buffer"), \
                     mock.patch("_psmux.capture_pane", return_value=""), \
                     mock.patch("_psmux.kill_session") as m_kill, \
                     mock.patch("_psmux_capture.extract_response", side_effect=_psmux_capture_mod.MarkerNotFoundError("no bullet found")), \
                     mock.patch.object(mod, "_wait_for_marker_in_pane", return_value=True), \
                     mock.patch.object(mod, "_wait_for_idle_prompt", return_value=True), \
                     mock.patch.object(mod, "_wait_for_idle_stable", return_value=True), \
                     mock.patch("_paths.resolve_git_root", return_value=tmpdir_path), \
                     mock.patch("_config.load_config", return_value={}), \
                     mock.patch("sys.stdout", new_callable=io.StringIO), \
                     mock.patch("sys.stderr", stderr_capture):

                    ret = mod.main()

                    assert ret == 1, f"S11: expected 1, got {ret}"
                    stderr_text = stderr_capture.getvalue()
                    assert "MarkerNotFoundError" in stderr_text, \
                        f"S11: expected 'MarkerNotFoundError' in stderr: {stderr_text}"
                    print("PASS: S11 (extract_response raises MarkerNotFoundError)")
            finally:
                sys.argv = saved_argv
                sys.stdin = saved_stdin
    except Exception as e:
        print(f"FAIL: S11 - {e}")
        errors += 1

    # ── S12: _resolve_shell_path reads config value ─────────────────────────
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            mod = _load_claude_sub_module()

            with mock.patch("_config.load_config", return_value={"llm": {"claude": {"psmux": {"shell_path": "C:/my/pwsh.exe"}}}}):
                result = mod._resolve_shell_path()
                assert result == "C:/my/pwsh.exe", f"S12: expected 'C:/my/pwsh.exe', got {result}"
                print("PASS: S12 (_resolve_shell_path reads config value)")
    except Exception as e:
        print(f"FAIL: S12 - {e}")
        errors += 1

    # ── S13: _resolve_shell_path defaults to pwsh ──────────────────────────
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            mod = _load_claude_sub_module()

            with mock.patch("_config.load_config", return_value={}):
                result = mod._resolve_shell_path()
                assert result == "pwsh", f"S13: expected 'pwsh', got {result}"
                print("PASS: S13 (_resolve_shell_path defaults to pwsh)")
    except Exception as e:
        print(f"FAIL: S13 - {e}")
        errors += 1

    # ── S14: new_session called with rows=100 ────────────────────────────────
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            mod = _load_claude_sub_module()
            tmpdir_path = Path(tmpdir)
            scratch_dir = tmpdir_path / ".scratch"
            scratch_dir.mkdir(exist_ok=True)

            def mock_list_sessions():
                return []

            def mock_capture_pane(session_name, **kwargs):
                return "  ❯ \n● ok\n  ❯ "

            def mock_extract_response(snapshot):
                return "ok"

            saved_argv = sys.argv[:]
            saved_stdin = sys.stdin
            try:
                sys.argv = [
                    str(_CLAUDE_SUB_PY),
                    "--mode", "bulk",
                    "--model", "claude-opus",
                ]
                sys.stdin = io.StringIO("test prompt")

                with mock.patch("_psmux.new_session") as m_new_session, \
                     mock.patch("_psmux.set_history_limit"), \
                     mock.patch("_psmux.list_sessions", side_effect=mock_list_sessions), \
                     mock.patch("_psmux.send_keys"), \
                     mock.patch("_psmux.load_buffer"), \
                     mock.patch("_psmux.paste_buffer"), \
                     mock.patch("_psmux.capture_pane", side_effect=mock_capture_pane), \
                     mock.patch("_psmux.kill_session"), \
                     mock.patch("_psmux_capture.extract_response", side_effect=mock_extract_response), \
                     mock.patch.object(mod, "_wait_for_marker_in_pane", return_value=True), \
                     mock.patch.object(mod, "_wait_for_idle_prompt", return_value=True), \
                     mock.patch.object(mod, "_wait_for_idle_stable", return_value=True), \
                     mock.patch("_paths.resolve_git_root", return_value=tmpdir_path), \
                     mock.patch("_config.load_config", return_value={}), \
                     mock.patch("sys.stdout", new_callable=io.StringIO):

                    ret = mod.main()

                    # Check that new_session was called
                    m_new_session.assert_called_once()
                    call_kwargs = m_new_session.call_args[1]
                    assert call_kwargs.get("rows") == 100, \
                        f"S14: expected rows=100, got {call_kwargs.get('rows')}"
                    assert ret == 0, f"S14: expected 0, got {ret}"
                    print("PASS: S14 (new_session called with rows=100)")
            finally:
                sys.argv = saved_argv
                sys.stdin = saved_stdin
    except Exception as e:
        print(f"FAIL: S14 - {e}")
        errors += 1

    # ── Direct unit tests for _wait_for_idle_stable ──────────────────────────
    try:
        mod = _load_claude_sub_module()
        _wait_for_idle_stable = mod._wait_for_idle_stable

        # Scenario (a): Phase 1 times out (no "esc to interrupt"), Phase 2 finds "for shortcuts" twice; return True
        try:
            with mock.patch("_psmux.capture_pane", side_effect=["? for shortcuts\n", "? for shortcuts\n", "? for shortcuts\n"]), \
                 mock.patch("time.sleep"), \
                 mock.patch("time.monotonic", side_effect=[0.0, 61.0, 0.0, 1.0]):
                result = _wait_for_idle_stable(session_name="s", timeout_s=5.0)
                assert result is True, f"Scenario (a): expected True, got {result}"
            print("[OK] _wait_for_idle_stable scenario (a)")
        except Exception as e:
            print(f"[FAIL] _wait_for_idle_stable scenario (a): {e}")
            errors += 1

        # Scenario (b): Phase 1 finds "esc to interrupt", Phase 2 finds "? for shortcuts" twice → True
        try:
            with mock.patch("_psmux.capture_pane", side_effect=["esc to interrupt\n", "? for shortcuts\n", "? for shortcuts\n"]), \
                 mock.patch("time.sleep"), \
                 mock.patch("time.monotonic", side_effect=[0.0, 1.0, 0.0, 1.0, 2.0]):
                result = _wait_for_idle_stable(session_name="s", timeout_s=5.0)
                assert result is True, f"Scenario (b): expected True, got {result}"
            print("[OK] _wait_for_idle_stable scenario (b)")
        except Exception as e:
            print(f"[FAIL] _wait_for_idle_stable scenario (b): {e}")
            errors += 1

        # Scenario (c): Phase 1 finds marker quickly, Phase 2 never finds "for shortcuts", timeout fires → returns False
        try:
            with mock.patch("_psmux.capture_pane", side_effect=["esc to interrupt\n", ""]), \
                 mock.patch("time.sleep"), \
                 mock.patch("time.monotonic", side_effect=[0.0, 0.0, 6.0]):
                result = _wait_for_idle_stable(session_name="s", timeout_s=5.0)
                assert result is False, f"Scenario (c): expected False, got {result}"
            print("[OK] _wait_for_idle_stable scenario (c)")
        except Exception as e:
            print(f"[FAIL] _wait_for_idle_stable scenario (c): {e}")
            errors += 1

    except Exception as e:
        print(f"FAIL: _wait_for_idle_stable unit tests - {e}")
        errors += 1

    # ── Direct unit tests for _wait_for_idle_prompt ──────────────────────────
    try:
        mod = _load_claude_sub_module()
        _wait_for_idle_prompt = mod._wait_for_idle_prompt

        # Scenario (d): capture returns "? for shortcuts" on the first call; return True
        try:
            with mock.patch("_psmux.capture_pane", return_value="? for shortcuts"), \
                 mock.patch("time.sleep"), \
                 mock.patch("time.monotonic", side_effect=[0.0, 0.0]):
                result = _wait_for_idle_prompt(session_name="s", timeout_s=5.0)
                assert result is True, f"Scenario (d): expected True, got {result}"
            print("[OK] _wait_for_idle_prompt scenario (d)")
        except Exception as e:
            print(f"[FAIL] _wait_for_idle_prompt scenario (d): {e}")
            errors += 1

        # Scenario (e): capture always returns "❯ " (never contains "for shortcuts"), timeout fires
        try:
            with mock.patch("_psmux.capture_pane", return_value="❯ "), \
                 mock.patch("time.sleep"), \
                 mock.patch("time.monotonic", side_effect=[0.0, 0.0, 6.0, 6.0]):
                result = _wait_for_idle_prompt(session_name="s", timeout_s=5.0)
                assert result is False, f"Scenario (e): expected False, got {result}"
            print("[OK] _wait_for_idle_prompt scenario (e)")
        except Exception as e:
            print(f"[FAIL] _wait_for_idle_prompt scenario (e): {e}")
            errors += 1

    except Exception as e:
        print(f"FAIL: _wait_for_idle_prompt unit tests - {e}")
        errors += 1

    return errors


if __name__ == "__main__":
    sys.exit(main())
