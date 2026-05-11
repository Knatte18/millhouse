"""Unit tests for plugins/mill/scripts/_llm_claude.py.

These tests exercise the pure-Python surface: argv construction,
stream-JSON parsing, exception hierarchy, signature shape. They do NOT
invoke the live ``claude`` CLI — those tests live in
``integration_tests/smoke-llm-claude.py``.
"""
from __future__ import annotations

import contextlib
import inspect
import io
import subprocess as _subprocess_mod
import sys
import unittest.mock as mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _llm_claude as _llm_claude_mod  # noqa: E402
import _subprocess_util as _subprocess_util_mod  # noqa: E402
from _llm_claude import (  # noqa: E402
    LLMError,
    LLMRateLimitError,
    LLMSessionError,
    _build_argv,
    _claude_argv_prefix,
    _parse_stream_json,
    _scan_rate_limit,
    run_bulk,
    run_implementer,
    run_tool_use,
)


def main() -> int:
    errors = 0

    # Module imports cleanly and public symbols exist
    assert callable(run_bulk)
    assert callable(run_tool_use)
    assert callable(run_implementer)
    assert issubclass(LLMError, Exception)
    assert issubclass(LLMSessionError, LLMError)
    assert issubclass(LLMRateLimitError, LLMError)
    print("PASS: module imports cleanly, public symbols present")

    # Function signatures (keyword-only model arg, session_id/resume present)
    for fn_name, fn in (("run_bulk", run_bulk), ("run_tool_use", run_tool_use),
                        ("run_implementer", run_implementer)):
        sig = inspect.signature(fn)
        assert "prompt_text" in sig.parameters, f"{fn_name}: missing prompt_text"
        assert "model" in sig.parameters, f"{fn_name}: missing model"
        assert "session_id" in sig.parameters, f"{fn_name}: missing session_id"
        assert "resume" in sig.parameters, f"{fn_name}: missing resume"
        assert sig.parameters["model"].kind == inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["session_id"].default is None
        assert sig.parameters["resume"].default is False
    assert "cwd" in inspect.signature(run_implementer).parameters
    assert "cwd" not in inspect.signature(run_bulk).parameters
    print("PASS: signatures have session_id/resume (cwd only on run_implementer)")

    # LLMError and LLMSessionError behave as expected
    try:
        raise LLMError("test error")
    except LLMError as e:
        assert str(e) == "test error"
        print("PASS: LLMError raises and str() works")

    try:
        raise LLMSessionError("stale session")
    except LLMError as e:
        assert str(e) == "stale session"
        print("PASS: LLMSessionError is caught as LLMError")

    # LLMRateLimitError class existence and hierarchy
    try:
        raise LLMRateLimitError("throttled")
    except LLMError as e:
        assert str(e) == "throttled"
        print("PASS: LLMRateLimitError is caught as LLMError")

    # _parse_stream_json: valid result event with session_id
    raw = (
        '{"type":"system","subtype":"init","session_id":"abc123"}\n'
        '{"type":"result","result":"APPROVE\\n\\nLooks good.","session_id":"abc123"}\n'
    )
    text, sid = _parse_stream_json(raw)
    assert "APPROVE" in text
    assert sid == "abc123"
    print("PASS: _parse_stream_json extracts result text + session_id")

    # _parse_stream_json: session_id from init only (no result sid)
    raw = (
        '{"type":"system","subtype":"init","session_id":"init-only"}\n'
        '{"type":"result","result":"OK"}\n'
    )
    text, sid = _parse_stream_json(raw)
    assert text == "OK" and sid == "init-only"
    print("PASS: _parse_stream_json falls back to init session_id")

    # _parse_stream_json: no session_id at all (returns None)
    text, sid = _parse_stream_json('{"type":"result","result":"OK"}\n')
    assert text == "OK" and sid is None
    print("PASS: _parse_stream_json returns None session_id when absent")

    # _parse_stream_json: no content -> LLMError
    try:
        _parse_stream_json('{"type":"other","data":"x"}\n')
        errors += 1
    except LLMError:
        print("PASS: _parse_stream_json no content -> LLMError")

    # _parse_stream_json: bad JSON line is skipped
    mixed = 'not-json\n{"type":"result","result":"OK","session_id":"s1"}\n'
    text, sid = _parse_stream_json(mixed)
    assert text == "OK" and sid == "s1"
    print("PASS: _parse_stream_json skips bad JSON line")

    # _scan_rate_limit: rate_limit_event type -> True
    rl_event = '{"type":"rate_limit_event","limit_type":"requests"}\n'
    assert _scan_rate_limit(rl_event) is True
    print("PASS: _scan_rate_limit rate_limit_event -> True")

    # _scan_rate_limit: result event with is_error + rate-limit subtype -> True
    rl_result = '{"type":"result","is_error":true,"subtype":"rate_limited","session_id":"s1"}\n'
    assert _scan_rate_limit(rl_result) is True
    print("PASS: _scan_rate_limit result+is_error+rate_limited subtype -> True")

    # _scan_rate_limit: result event with is_error + generic subtype + no rate-limit string -> False
    generic_err = '{"type":"result","is_error":true,"subtype":"error_during_execution","session_id":"s1"}\n'
    assert _scan_rate_limit(generic_err) is False
    print("PASS: _scan_rate_limit result+is_error+generic subtype -> False")

    # _scan_rate_limit: empty stdout -> False
    assert _scan_rate_limit("") is False
    print("PASS: _scan_rate_limit empty stdout -> False")

    # _scan_rate_limit: unparseable line then rate_limit_event -> True (defensive parse)
    mixed_rl = 'not-valid-json\n{"type":"rate_limit_event"}\n'
    assert _scan_rate_limit(mixed_rl) is True
    print("PASS: _scan_rate_limit bad line + rate_limit_event -> True")

    # _scan_rate_limit: unparseable line then generic result error -> False
    mixed_generic = 'not-valid-json\n{"type":"result","is_error":true,"subtype":"error_during_execution"}\n'
    assert _scan_rate_limit(mixed_generic) is False
    print("PASS: _scan_rate_limit bad line + generic error -> False")

    # _build_argv: bulk (no effort, no session)
    prefix = _claude_argv_prefix()
    argv = _build_argv("claude-sonnet-4-5", None, "")
    assert argv == [*prefix, "-p", "--output-format", "stream-json", "--verbose",
                    "--model", "claude-sonnet-4-5", "--allowedTools", ""]
    print("PASS: _build_argv bulk without effort / without session")

    # _build_argv: tool-use with effort
    argv = _build_argv("claude-sonnet-4-5", "max", "Read,Grep,Glob")
    assert "--effort" in argv and "max" in argv
    assert "Read,Grep,Glob" in argv
    print("PASS: _build_argv tool-use with effort")

    # _build_argv: --session-id when session given, resume=False
    argv = _build_argv("claude-sonnet-4-5", None, "", session_id="my-uuid", resume=False)
    assert "--session-id" in argv and "my-uuid" in argv
    assert "--resume" not in argv
    print("PASS: _build_argv emits --session-id for new session with chosen id")

    # _build_argv: --resume when resume=True
    argv = _build_argv("claude-sonnet-4-5", None, "", session_id="my-uuid", resume=True)
    assert "--resume" in argv and "my-uuid" in argv
    assert "--session-id" not in argv
    print("PASS: _build_argv emits --resume when resume=True")

    # _build_argv: resume=True without session_id -> LLMError
    try:
        _build_argv("claude-sonnet-4-5", None, "", session_id=None, resume=True)
        errors += 1
    except LLMError:
        print("PASS: _build_argv rejects resume=True without session_id")

    # _invoke integration: monkeypatch _subprocess_util.run
    _RL_STDOUT = '{"type":"rate_limit_event","limit_type":"requests"}\n'
    _GENERIC_ERR_STDOUT = '{"type":"result","is_error":true,"subtype":"error_during_execution"}\n'
    _GOOD_STDOUT = (
        '{"type":"system","subtype":"init","session_id":"sid-xyz"}\n'
        '{"type":"result","result":"All good","session_id":"sid-xyz"}\n'
    )

    _orig_run = _subprocess_util_mod.run

    def _fake_rl(argv, **kwargs):
        return _subprocess_mod.CompletedProcess(args=argv, returncode=1, stdout=_RL_STDOUT, stderr="rate limited")

    def _fake_generic(argv, **kwargs):
        return _subprocess_mod.CompletedProcess(args=argv, returncode=1, stdout=_GENERIC_ERR_STDOUT, stderr="crash")

    def _fake_ok(argv, **kwargs):
        return _subprocess_mod.CompletedProcess(args=argv, returncode=0, stdout=_GOOD_STDOUT, stderr="")

    try:
        # rate-limited exit + resume=False -> LLMRateLimitError
        _subprocess_util_mod.run = _fake_rl
        try:
            run_bulk(prompt_text="x", model="m", session_id="abc", resume=False)
            errors += 1
        except LLMRateLimitError:
            print("PASS: _invoke raises LLMRateLimitError on rate-limited exit (resume=False)")
        except Exception as exc:
            errors += 1
            print(f"FAIL: expected LLMRateLimitError, got {type(exc).__name__}: {exc}", file=sys.stderr)

        # rate-limited exit + resume=True -> LLMRateLimitError (takes precedence over LLMSessionError)
        _subprocess_util_mod.run = _fake_rl
        try:
            run_bulk(prompt_text="x", model="m", session_id="abc", resume=True)
            errors += 1
        except LLMRateLimitError:
            print("PASS: _invoke raises LLMRateLimitError on rate-limited exit (resume=True)")
        except Exception as exc:
            errors += 1
            print(f"FAIL: expected LLMRateLimitError, got {type(exc).__name__}: {exc}", file=sys.stderr)

        # generic error + resume=True -> LLMSessionError
        _subprocess_util_mod.run = _fake_generic
        try:
            run_bulk(prompt_text="x", model="m", session_id="abc", resume=True)
            errors += 1
        except LLMSessionError:
            print("PASS: _invoke raises LLMSessionError on generic error with resume=True")
        except Exception as exc:
            errors += 1
            print(f"FAIL: expected LLMSessionError, got {type(exc).__name__}: {exc}", file=sys.stderr)

        # generic error + resume=False -> LLMError but NOT LLMSessionError
        _subprocess_util_mod.run = _fake_generic
        try:
            run_bulk(prompt_text="x", model="m", session_id=None, resume=False)
            errors += 1
        except LLMSessionError:
            errors += 1
            print("FAIL: got LLMSessionError but expected plain LLMError", file=sys.stderr)
        except LLMError:
            print("PASS: _invoke raises plain LLMError (not LLMSessionError) on generic error with resume=False")

        # zero exit -> (text, sid) tuple unchanged
        _subprocess_util_mod.run = _fake_ok
        result_tuple = run_bulk(prompt_text="x", model="m", session_id="sid-xyz", resume=False)
        assert result_tuple == ("All good", "sid-xyz"), f"unexpected result: {result_tuple}"
        print("PASS: _invoke zero-exit returns (text, sid) unchanged")

    finally:
        _subprocess_util_mod.run = _orig_run

    # run_implementer passes Skill in --allowedTools
    _FAKE_STDOUT = (
        '{"type":"system","session_id":"fake-sid-123"}\n'
        '{"type":"result","result":"done","session_id":"fake-sid-123"}\n'
    )

    class _FakeResult:
        returncode = 0
        stdout = _FAKE_STDOUT
        stderr = ""

    captured_argv: list[str] = []

    def _fake_run(argv: list[str], **_kwargs: object) -> _FakeResult:
        captured_argv.extend(argv)
        return _FakeResult()

    with mock.patch.object(_subprocess_util_mod, "run", _fake_run):
        run_implementer("hello", model="claude-sonnet-4-5", session_id="fake-sid-123")

    assert "--allowedTools" in captured_argv, "--allowedTools flag missing from argv"
    tools_idx = captured_argv.index("--allowedTools")
    tools_value = captured_argv[tools_idx + 1]
    assert tools_value == "Read,Edit,Write,Bash,Grep,Glob,Skill", (
        f"unexpected tools: {tools_value!r}"
    )
    print(f"PASS: run_implementer uses --allowedTools {tools_value}")

    # rate-limit error message includes stdout fallback content
    with mock.patch.object(
        _subprocess_util_mod,
        "run",
        lambda argv, **kw: _subprocess_mod.CompletedProcess(
            args=[],
            returncode=1,
            stdout='{"type":"rate_limit_event","limit_type":"requests"}\n',
            stderr="",
        ),
    ):
        try:
            run_bulk("ignored prompt", model="claude-sonnet-4-6")
            errors += 1
            print("FAIL: expected LLMRateLimitError, no exception raised", file=sys.stderr)
        except LLMRateLimitError as e:
            if "rate_limit_event" not in str(e):
                errors += 1
                print(f"FAIL: stdout content missing from rate-limit message: {e}", file=sys.stderr)
            else:
                print("PASS: rate-limit error message includes stdout fallback content")
        except Exception as exc:
            errors += 1
            print(f"FAIL: expected LLMRateLimitError, got {type(exc).__name__}: {exc}", file=sys.stderr)

    # --- fast-fail retry path ---
    _RETRY_OK_STDOUT = '{"type":"result","result":"ok","session_id":"abc"}\n'

    # test_invoke_retries_on_fast_fail_then_succeeds
    _retry_call_count = [0]

    def _fast_fail_then_ok(argv, **kwargs):
        _retry_call_count[0] += 1
        if _retry_call_count[0] == 1:
            return _subprocess_mod.CompletedProcess(args=argv, returncode=1, stdout="", stderr="shim fail")
        return _subprocess_mod.CompletedProcess(args=argv, returncode=0, stdout=_RETRY_OK_STDOUT, stderr="")

    _retry_call_count[0] = 0
    _stderr_buf = io.StringIO()
    with mock.patch.object(_subprocess_util_mod, "run", _fast_fail_then_ok):
        with contextlib.redirect_stderr(_stderr_buf):
            _retry_result = run_bulk("prompt", model="m")
    if _retry_call_count[0] != 2:
        errors += 1
        print(f"FAIL: expected 2 calls, got {_retry_call_count[0]}", file=sys.stderr)
    elif "fast-fail retry" not in _stderr_buf.getvalue():
        errors += 1
        print("FAIL: 'fast-fail retry' not found in stderr", file=sys.stderr)
    elif _retry_result != ("ok", "abc"):
        errors += 1
        print(f"FAIL: unexpected retry result: {_retry_result}", file=sys.stderr)
    else:
        print("PASS: _invoke retries on fast-fail then succeeds (2 calls, breadcrumb emitted)")

    # test_invoke_does_not_retry_on_slow_fail
    _slow_call_count = [0]

    def _slow_fail(argv, **kwargs):
        _slow_call_count[0] += 1
        return _subprocess_mod.CompletedProcess(args=argv, returncode=1, stdout="", stderr="slow fail")

    _slow_call_count[0] = 0
    with mock.patch.object(_subprocess_util_mod, "run", _slow_fail):
        with mock.patch.object(_llm_claude_mod.time, "monotonic", side_effect=[0.0, 3.0]):
            try:
                run_bulk("prompt", model="m")
                errors += 1
                print("FAIL: expected LLMError on slow fail, no exception raised", file=sys.stderr)
            except LLMError:
                if _slow_call_count[0] != 1:
                    errors += 1
                    print(f"FAIL: expected 1 call on slow fail, got {_slow_call_count[0]}", file=sys.stderr)
                else:
                    print("PASS: _invoke does not retry on slow fail (dt >= 2.0s)")
            except Exception as exc:
                errors += 1
                print(f"FAIL: expected LLMError on slow fail, got {type(exc).__name__}: {exc}", file=sys.stderr)

    # test_invoke_does_not_retry_when_resume_true
    _resume_call_count = [0]

    def _fast_fail_resume(argv, **kwargs):
        _resume_call_count[0] += 1
        return _subprocess_mod.CompletedProcess(args=argv, returncode=1, stdout="", stderr="shim fail")

    _resume_call_count[0] = 0
    with mock.patch.object(_subprocess_util_mod, "run", _fast_fail_resume):
        try:
            run_bulk("prompt", model="m", session_id="abc", resume=True)
            errors += 1
            print("FAIL: expected LLMSessionError with resume=True, no exception raised", file=sys.stderr)
        except LLMSessionError:
            if _resume_call_count[0] != 1:
                errors += 1
                print(f"FAIL: expected 1 call with resume=True, got {_resume_call_count[0]}", file=sys.stderr)
            else:
                print("PASS: _invoke does not retry when resume=True (raises LLMSessionError, 1 call)")
        except Exception as exc:
            errors += 1
            print(f"FAIL: expected LLMSessionError, got {type(exc).__name__}: {exc}", file=sys.stderr)

    # test_invoke_does_not_retry_on_rate_limit
    _rl_fast_call_count = [0]

    def _rate_limit_fast(argv, **kwargs):
        _rl_fast_call_count[0] += 1
        return _subprocess_mod.CompletedProcess(
            args=argv, returncode=1,
            stdout='{"type":"rate_limit_event","limit_type":"requests"}\n',
            stderr="rate limited",
        )

    _rl_fast_call_count[0] = 0
    with mock.patch.object(_subprocess_util_mod, "run", _rate_limit_fast):
        try:
            run_bulk("prompt", model="m")
            errors += 1
            print("FAIL: expected LLMRateLimitError, no exception raised", file=sys.stderr)
        except LLMRateLimitError:
            if _rl_fast_call_count[0] != 1:
                errors += 1
                print(f"FAIL: expected 1 call on rate-limit, got {_rl_fast_call_count[0]}", file=sys.stderr)
            else:
                print("PASS: _invoke does not retry on rate-limit (raises LLMRateLimitError, 1 call)")
        except Exception as exc:
            errors += 1
            print(f"FAIL: expected LLMRateLimitError, got {type(exc).__name__}: {exc}", file=sys.stderr)

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _llm_claude unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
