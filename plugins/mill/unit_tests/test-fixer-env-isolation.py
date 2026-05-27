"""Unit tests for _llm_claude._invoke env stripping.

Tests that _invoke removes the seven named git-state env vars
before spawning Claude sessions, preventing worktree-local config
from polluting subprocess author identity.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest.mock as mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _llm_claude as _llm_claude_mod  # noqa: E402
import _subprocess_util as _subprocess_util_mod  # noqa: E402


def _make_minimal_response() -> str:
    """Create a minimal stream-json response that _parse_stream_json accepts."""
    return json.dumps({
        "type": "result",
        "result": "ok",
        "session_id": "test-session"
    })


def main() -> int:
    errors = 0

    # Test 1: strips seven named vars (psmux branch)
    try:
        with mock.patch.dict(os.environ, {
            "GIT_DIR": "/x",
            "GIT_WORK_TREE": "/y",
            "GIT_INDEX_FILE": "/z",
            "GIT_AUTHOR_NAME": "A",
            "GIT_AUTHOR_EMAIL": "a@b",
            "GIT_COMMITTER_NAME": "C",
            "GIT_COMMITTER_EMAIL": "c@d",
            "PATH": "/bin",
            "HOME": "/h",
        }, clear=False):
            captured_env = None

            def capture_run(*args, **kwargs):
                nonlocal captured_env
                captured_env = kwargs.get("env")
                return subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout=_make_minimal_response(),
                    stderr=""
                )

            with mock.patch.object(_subprocess_util_mod, "run", side_effect=capture_run):
                with mock.patch.object(_llm_claude_mod, "_get_via_psmux_flag", return_value=True):
                    result, session_id = _llm_claude_mod._invoke(
                        "test prompt",
                        model="claude-opus-4-7",
                        timeout=30,
                        cwd=None
                    )

            assert captured_env is not None, "env was not captured from run() call"
            assert "GIT_DIR" not in captured_env, "GIT_DIR was not stripped"
            assert "GIT_WORK_TREE" not in captured_env, "GIT_WORK_TREE was not stripped"
            assert "GIT_INDEX_FILE" not in captured_env, "GIT_INDEX_FILE was not stripped"
            assert "GIT_AUTHOR_NAME" not in captured_env, "GIT_AUTHOR_NAME was not stripped"
            assert "GIT_AUTHOR_EMAIL" not in captured_env, "GIT_AUTHOR_EMAIL was not stripped"
            assert "GIT_COMMITTER_NAME" not in captured_env, "GIT_COMMITTER_NAME was not stripped"
            assert "GIT_COMMITTER_EMAIL" not in captured_env, "GIT_COMMITTER_EMAIL was not stripped"
            assert "PATH" in captured_env, "PATH was incorrectly stripped"
            assert "HOME" in captured_env, "HOME was incorrectly stripped"
            print("PASS: strips seven named vars (psmux branch)")
    except Exception as e:
        print(f"FAIL: test_strips_seven_vars_psmux: {e}")
        errors += 1

    # Test 2: strips seven named vars (direct branch)
    try:
        with mock.patch.dict(os.environ, {
            "GIT_DIR": "/x",
            "GIT_WORK_TREE": "/y",
            "GIT_INDEX_FILE": "/z",
            "GIT_AUTHOR_NAME": "A",
            "GIT_AUTHOR_EMAIL": "a@b",
            "GIT_COMMITTER_NAME": "C",
            "GIT_COMMITTER_EMAIL": "c@d",
            "PATH": "/bin",
            "HOME": "/h",
        }, clear=False):
            captured_env = None

            def capture_run(*args, **kwargs):
                nonlocal captured_env
                captured_env = kwargs.get("env")
                return subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout=_make_minimal_response(),
                    stderr=""
                )

            with mock.patch.object(_subprocess_util_mod, "run", side_effect=capture_run):
                with mock.patch.object(_llm_claude_mod, "_get_via_psmux_flag", return_value=False):
                    result, session_id = _llm_claude_mod._invoke(
                        "test prompt",
                        model="claude-opus-4-7",
                        timeout=30,
                        cwd=None
                    )

            assert captured_env is not None, "env was not captured from run() call"
            assert "GIT_DIR" not in captured_env, "GIT_DIR was not stripped"
            assert "GIT_WORK_TREE" not in captured_env, "GIT_WORK_TREE was not stripped"
            assert "GIT_INDEX_FILE" not in captured_env, "GIT_INDEX_FILE was not stripped"
            assert "GIT_AUTHOR_NAME" not in captured_env, "GIT_AUTHOR_NAME was not stripped"
            assert "GIT_AUTHOR_EMAIL" not in captured_env, "GIT_AUTHOR_EMAIL was not stripped"
            assert "GIT_COMMITTER_NAME" not in captured_env, "GIT_COMMITTER_NAME was not stripped"
            assert "GIT_COMMITTER_EMAIL" not in captured_env, "GIT_COMMITTER_EMAIL was not stripped"
            assert "PATH" in captured_env, "PATH was incorrectly stripped"
            assert "HOME" in captured_env, "HOME was incorrectly stripped"
            print("PASS: strips seven named vars (direct branch)")
    except Exception as e:
        print(f"FAIL: test_strips_seven_vars_direct: {e}")
        errors += 1

    # Test 3: preserves benign git vars
    try:
        with mock.patch.dict(os.environ, {
            "GIT_PAGER": "less",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_GLOBAL": "/tmp/cfg",
            "GIT_PYTHON_REFRESH": "quiet",
        }, clear=False):
            captured_env = None

            def capture_run(*args, **kwargs):
                nonlocal captured_env
                captured_env = kwargs.get("env")
                return subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout=_make_minimal_response(),
                    stderr=""
                )

            with mock.patch.object(_subprocess_util_mod, "run", side_effect=capture_run):
                with mock.patch.object(_llm_claude_mod, "_get_via_psmux_flag", return_value=False):
                    result, session_id = _llm_claude_mod._invoke(
                        "test prompt",
                        model="claude-opus-4-7",
                        timeout=30,
                        cwd=None
                    )

            assert captured_env is not None, "env was not captured"
            assert captured_env.get("GIT_PAGER") == "less", "GIT_PAGER was not preserved"
            assert captured_env.get("GIT_TERMINAL_PROMPT") == "0", "GIT_TERMINAL_PROMPT was not preserved"
            assert captured_env.get("GIT_CONFIG_GLOBAL") == "/tmp/cfg", "GIT_CONFIG_GLOBAL was not preserved"
            assert captured_env.get("GIT_PYTHON_REFRESH") == "quiet", "GIT_PYTHON_REFRESH was not preserved"
            print("PASS: preserves benign git vars")
    except Exception as e:
        print(f"FAIL: test_preserves_benign_git_vars: {e}")
        errors += 1

    # Test 4: preserves unrelated vars
    try:
        with mock.patch.dict(os.environ, {
            "PATH": "/x:/y",
            "HOME": "/h",
            "CLAUDE_PLUGIN_ROOT": "/p",
            "PYTHONPATH": "/q",
        }, clear=False):
            captured_env = None

            def capture_run(*args, **kwargs):
                nonlocal captured_env
                captured_env = kwargs.get("env")
                return subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout=_make_minimal_response(),
                    stderr=""
                )

            with mock.patch.object(_subprocess_util_mod, "run", side_effect=capture_run):
                with mock.patch.object(_llm_claude_mod, "_get_via_psmux_flag", return_value=False):
                    result, session_id = _llm_claude_mod._invoke(
                        "test prompt",
                        model="claude-opus-4-7",
                        timeout=30,
                        cwd=None
                    )

            assert captured_env is not None, "env was not captured"
            assert captured_env.get("PATH") == "/x:/y", "PATH was not preserved"
            assert captured_env.get("HOME") == "/h", "HOME was not preserved"
            assert captured_env.get("CLAUDE_PLUGIN_ROOT") == "/p", "CLAUDE_PLUGIN_ROOT was not preserved"
            assert captured_env.get("PYTHONPATH") == "/q", "PYTHONPATH was not preserved"
            print("PASS: preserves unrelated vars")
    except Exception as e:
        print(f"FAIL: test_preserves_unrelated_vars: {e}")
        errors += 1

    # Test 5: STRIP_VARS constant is exact
    try:
        expected = {
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_INDEX_FILE",
            "GIT_AUTHOR_NAME",
            "GIT_AUTHOR_EMAIL",
            "GIT_COMMITTER_NAME",
            "GIT_COMMITTER_EMAIL",
        }
        actual = _llm_claude_mod.STRIP_VARS
        assert actual == expected, f"STRIP_VARS mismatch: expected {expected}, got {actual}"
        print("PASS: STRIP_VARS constant is exact")
    except AttributeError as e:
        print(f"FAIL: test_strip_constant_is_exact_set: STRIP_VARS not defined: {e}")
        errors += 1
    except AssertionError as e:
        print(f"FAIL: test_strip_constant_is_exact_set: {e}")
        errors += 1
    except Exception as e:
        print(f"FAIL: test_strip_constant_is_exact_set: {e}")
        errors += 1

    if errors == 0:
        print("\n5 tests passed")
        return 0
    else:
        print(f"\n{errors} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
