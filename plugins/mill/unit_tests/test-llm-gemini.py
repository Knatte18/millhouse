"""Unit tests for plugins/mill/scripts/_llm_gemini.py.

These tests exercise the pure-Python surface: argv construction,
stream-JSON parsing, exception hierarchy, signature shape, and the
session-reuse short-circuit. They do NOT invoke the live ``gemini`` CLI —
those tests live in ``integration_tests/smoke-llm-gemini.py``.
"""
from __future__ import annotations

import inspect
import subprocess as _subprocess_mod
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _subprocess_util as _subprocess_util_mod  # noqa: E402
from _llm_gemini import (  # noqa: E402
    LLMError,
    LLMRateLimitError,
    LLMSessionError,
    _build_argv,
    _gemini_argv_prefix,
    _parse_gemini_stream_json,
    _scan_gemini_rate_limit,
    run_bulk,
    run_tool_use,
)


def main() -> int:
    errors = 0

    # ------------------------------------------------------------------
    # Module imports cleanly + public symbols exist
    # ------------------------------------------------------------------
    assert callable(run_bulk)
    assert callable(run_tool_use)
    assert issubclass(LLMError, Exception)
    assert issubclass(LLMSessionError, LLMError)
    assert issubclass(LLMRateLimitError, LLMError)
    print("PASS: module imports cleanly, public symbols present")

    # ------------------------------------------------------------------
    # Signature shape
    # ------------------------------------------------------------------
    for fn_name, fn in (("run_bulk", run_bulk), ("run_tool_use", run_tool_use)):
        sig = inspect.signature(fn)
        params = sig.parameters
        for pname in ("prompt_text", "model", "effort", "timeout", "session_id", "resume"):
            assert pname in params, f"{fn_name}: missing {pname}"
        assert params["model"].kind == inspect.Parameter.KEYWORD_ONLY, f"{fn_name}: model not keyword-only"
        assert params["session_id"].default is None, f"{fn_name}: session_id default != None"
        assert params["resume"].default is False, f"{fn_name}: resume default != False"
        assert params["effort"].default is None, f"{fn_name}: effort default != None"
        assert "cwd" not in params, f"{fn_name}: unexpected cwd param (run_implementer is out of scope)"
    print("PASS: signatures have correct parameters (model keyword-only, no cwd)")

    # ------------------------------------------------------------------
    # Exception hierarchy round-trip
    # ------------------------------------------------------------------
    try:
        raise LLMError("base error")
    except LLMError as e:
        assert str(e) == "base error"
        print("PASS: LLMError raises and str() round-trips")

    try:
        raise LLMSessionError("stale session")
    except LLMError as e:
        assert str(e) == "stale session"
        print("PASS: LLMSessionError is caught as LLMError")

    try:
        raise LLMRateLimitError("throttled")
    except LLMError as e:
        assert str(e) == "throttled"
        print("PASS: LLMRateLimitError is caught as LLMError")

    # ------------------------------------------------------------------
    # _build_argv: bulk mode appends -e ""
    # ------------------------------------------------------------------
    prefix = _gemini_argv_prefix()
    argv = _build_argv("gemini-2.5-flash", tooluse=False)
    expected = [*prefix, "-p", "", "-o", "stream-json", "-m", "gemini-2.5-flash", "--approval-mode", "plan", "-e", ""]
    assert argv == expected, f"bulk argv mismatch: {argv!r}"
    print("PASS: _build_argv bulk appends -e ''")

    # ------------------------------------------------------------------
    # _build_argv: tool-use mode has no -e ""
    # ------------------------------------------------------------------
    argv = _build_argv("gemini-2.5-flash", tooluse=True)
    expected = [*prefix, "-p", "", "-o", "stream-json", "-m", "gemini-2.5-flash", "--approval-mode", "plan"]
    assert argv == expected, f"tool-use argv mismatch: {argv!r}"
    print("PASS: _build_argv tool-use has no -e ''")

    # ------------------------------------------------------------------
    # _parse_gemini_stream_json: current format — message/assistant with string content
    # ------------------------------------------------------------------
    raw = (
        '{"type":"init","session_id":"sid-init","model":"gemini-2.5-flash"}\n'
        '{"type":"message","role":"user","content":"prompt"}\n'
        '{"type":"message","role":"assistant","content":"APPROVE","delta":true,"session_id":"sid-init"}\n'
        '{"type":"result","status":"success","stats":{}}\n'
    )
    text, sid = _parse_gemini_stream_json(raw)
    assert text == "APPROVE" and sid == "sid-init", f"message/assistant parse: {(text, sid)!r}"
    print("PASS: _parse_gemini_stream_json message/assistant (current format) returns (text, session_id)")

    # ------------------------------------------------------------------
    # _parse_gemini_stream_json: current format — multi-chunk delta streaming
    # ------------------------------------------------------------------
    raw = (
        '{"type":"init","session_id":"sid-delta"}\n'
        '{"type":"message","role":"assistant","content":"ver","delta":true}\n'
        '{"type":"message","role":"assistant","content":"dict: APPROVE","delta":true}\n'
        '{"type":"result","status":"success","stats":{}}\n'
    )
    text, sid = _parse_gemini_stream_json(raw)
    assert text == "verdict: APPROVE" and sid == "sid-delta", f"delta chunks: {(text, sid)!r}"
    print("PASS: _parse_gemini_stream_json concatenates delta assistant chunks")

    # ------------------------------------------------------------------
    # _parse_gemini_stream_json: legacy result event with inline text
    # ------------------------------------------------------------------
    raw = '{"type":"system","subtype":"init","session_id":"abc"}\n{"type":"result","result":"APPROVE","session_id":"abc"}\n'
    text, sid = _parse_gemini_stream_json(raw)
    assert text == "APPROVE" and sid == "abc", f"result parse: {(text, sid)!r}"
    print("PASS: _parse_gemini_stream_json legacy result event returns (text, session_id)")

    # ------------------------------------------------------------------
    # _parse_gemini_stream_json: legacy assistant event
    # ------------------------------------------------------------------
    raw = '{"type":"assistant","message":{"content":[{"type":"text","text":"OK"}]},"session_id":"sid1"}\n'
    text, sid = _parse_gemini_stream_json(raw)
    assert text == "OK" and sid == "sid1", f"assistant parse: {(text, sid)!r}"
    print("PASS: _parse_gemini_stream_json legacy assistant event returns (text, session_id)")

    # ------------------------------------------------------------------
    # _parse_gemini_stream_json: system-only -> LLMError
    # ------------------------------------------------------------------
    try:
        _parse_gemini_stream_json('{"type":"system","subtype":"init","session_id":"sid-init"}\n')
        errors += 1
        print("FAIL: expected LLMError for system-only input", file=sys.stderr)
    except LLMError as e:
        assert "gemini returned no content" in str(e), f"unexpected message: {e}"
        print("PASS: _parse_gemini_stream_json system-only -> LLMError 'gemini returned no content'")

    # ------------------------------------------------------------------
    # _parse_gemini_stream_json: bad JSON line is skipped
    # ------------------------------------------------------------------
    mixed = 'not-json\n{"type":"result","result":"OK","session_id":"s1"}\n'
    text, sid = _parse_gemini_stream_json(mixed)
    assert text == "OK" and sid == "s1", f"bad-json skip: {(text, sid)!r}"
    print("PASS: _parse_gemini_stream_json skips bad JSON line")

    # ------------------------------------------------------------------
    # _scan_gemini_rate_limit: positives (stdout only)
    # ------------------------------------------------------------------
    for signal in ("RESOURCE_EXHAUSTED", "rate_limit", "rate limit", "QUOTA exceeded", "HTTP 429", "too many requests"):
        assert _scan_gemini_rate_limit(signal, "") is True, f"expected True for {signal!r}"
    print("PASS: _scan_gemini_rate_limit detects all positive signals in stdout")

    # ------------------------------------------------------------------
    # _scan_gemini_rate_limit: negatives
    # ------------------------------------------------------------------
    assert _scan_gemini_rate_limit("", "") is False
    assert _scan_gemini_rate_limit("foo", "bar") is False
    assert _scan_gemini_rate_limit("Internal error", "stack trace") is False
    print("PASS: _scan_gemini_rate_limit returns False for non-rate-limit strings")

    # ------------------------------------------------------------------
    # _scan_gemini_rate_limit: stderr path
    # ------------------------------------------------------------------
    assert _scan_gemini_rate_limit("", "RESOURCE_EXHAUSTED: quota exceeded") is True
    assert _scan_gemini_rate_limit("", "HTTP 429 too many requests") is True
    print("PASS: _scan_gemini_rate_limit detects signals in stderr when stdout is empty")

    # ------------------------------------------------------------------
    # _invoke zero-exit: monkeypatched _subprocess_util.run
    # ------------------------------------------------------------------
    _GOOD_STDOUT = '{"type":"result","result":"OK","session_id":"sid-z"}\n'
    _orig_run = _subprocess_util_mod.run
    try:
        _subprocess_util_mod.run = lambda argv, **kw: _subprocess_mod.CompletedProcess(
            args=argv, returncode=0, stdout=_GOOD_STDOUT, stderr=""
        )
        result = run_bulk("p", model="gemini-2.5-flash")
        assert result == ("OK", "sid-z"), f"zero-exit: {result!r}"
        print("PASS: _invoke zero-exit returns (text, session_id)")
    finally:
        _subprocess_util_mod.run = _orig_run

    # ------------------------------------------------------------------
    # _invoke zero-exit: synthetic session_id when none emitted
    # ------------------------------------------------------------------
    _NO_SID_STDOUT = '{"type":"result","result":"hello"}\n'
    _orig_run = _subprocess_util_mod.run
    try:
        _subprocess_util_mod.run = lambda argv, **kw: _subprocess_mod.CompletedProcess(
            args=argv, returncode=0, stdout=_NO_SID_STDOUT, stderr=""
        )
        text, sid = run_bulk("p", model="gemini-2.5-flash")
        assert text == "hello", f"text mismatch: {text!r}"
        assert sid.startswith("gemini-"), f"synthetic sid should start with 'gemini-': {sid!r}"
        print("PASS: _invoke synthesizes session_id prefixed 'gemini-' when CLI emits none")
    finally:
        _subprocess_util_mod.run = _orig_run

    # ------------------------------------------------------------------
    # _invoke non-zero + rate-limit -> LLMRateLimitError
    # ------------------------------------------------------------------
    _orig_run = _subprocess_util_mod.run
    try:
        _subprocess_util_mod.run = lambda argv, **kw: _subprocess_mod.CompletedProcess(
            args=argv, returncode=1, stdout="RESOURCE_EXHAUSTED: try again later", stderr=""
        )
        try:
            run_bulk("p", model="m")
            errors += 1
            print("FAIL: expected LLMRateLimitError", file=sys.stderr)
        except LLMRateLimitError as e:
            assert "RESOURCE_EXHAUSTED" in str(e), f"msg missing detail: {e}"
            print("PASS: _invoke non-zero + rate-limit -> LLMRateLimitError with detail")
        except Exception as exc:
            errors += 1
            print(f"FAIL: expected LLMRateLimitError, got {type(exc).__name__}: {exc}", file=sys.stderr)
    finally:
        _subprocess_util_mod.run = _orig_run

    # ------------------------------------------------------------------
    # _invoke non-zero + generic -> LLMError (not LLMRateLimitError)
    # ------------------------------------------------------------------
    _orig_run = _subprocess_util_mod.run
    try:
        _subprocess_util_mod.run = lambda argv, **kw: _subprocess_mod.CompletedProcess(
            args=argv, returncode=1, stdout="", stderr="boom"
        )
        try:
            run_bulk("p", model="m")
            errors += 1
            print("FAIL: expected LLMError", file=sys.stderr)
        except LLMRateLimitError:
            errors += 1
            print("FAIL: got LLMRateLimitError but expected plain LLMError", file=sys.stderr)
        except LLMError as e:
            assert "boom" in str(e), f"stderr missing from msg: {e}"
            print("PASS: _invoke non-zero + generic -> plain LLMError with stderr detail")
    finally:
        _subprocess_util_mod.run = _orig_run

    # ------------------------------------------------------------------
    # _invoke resume=True short-circuits before spawning subprocess
    # ------------------------------------------------------------------
    call_count = 0

    def _sentinel(argv, **kw):
        nonlocal call_count
        call_count += 1
        return _subprocess_mod.CompletedProcess(args=argv, returncode=0, stdout=_GOOD_STDOUT, stderr="")

    _orig_run = _subprocess_util_mod.run
    try:
        _subprocess_util_mod.run = _sentinel
        try:
            run_bulk("p", model="m", session_id="anything", resume=True)
            errors += 1
            print("FAIL: expected LLMSessionError for resume=True", file=sys.stderr)
        except LLMSessionError:
            assert call_count == 0, f"subprocess was spawned {call_count} time(s) despite resume=True"
            print("PASS: _invoke resume=True raises LLMSessionError without spawning subprocess")
        except Exception as exc:
            errors += 1
            print(f"FAIL: expected LLMSessionError, got {type(exc).__name__}: {exc}", file=sys.stderr)
    finally:
        _subprocess_util_mod.run = _orig_run

    # ------------------------------------------------------------------
    # _invoke timeout -> LLMError with "timed out" and timeout value
    # ------------------------------------------------------------------
    _orig_run = _subprocess_util_mod.run
    try:
        _subprocess_util_mod.run = lambda argv, **kw: (_ for _ in ()).throw(
            _subprocess_mod.TimeoutExpired(cmd=["x"], timeout=1.0)
        )
        try:
            run_bulk("p", model="m", timeout=1)
            errors += 1
            print("FAIL: expected LLMError for timeout", file=sys.stderr)
        except LLMError as e:
            msg = str(e).lower()
            assert "timed out" in msg, f"'timed out' not in message: {e}"
            assert "1" in str(e), f"timeout value not in message: {e}"
            print("PASS: _invoke timeout -> LLMError with 'timed out' and timeout value")
        except Exception as exc:
            errors += 1
            print(f"FAIL: expected LLMError, got {type(exc).__name__}: {exc}", file=sys.stderr)
    finally:
        _subprocess_util_mod.run = _orig_run

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _llm_gemini unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
