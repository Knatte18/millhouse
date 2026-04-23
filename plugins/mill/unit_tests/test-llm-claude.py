"""Unit tests for plugins/mill/scripts/_llm_claude.py.

These tests exercise the pure-Python surface: argv construction,
stream-JSON parsing, exception hierarchy, signature shape. They do NOT
invoke the live ``claude`` CLI — those tests live in
``integration_tests/smoke-llm-claude.py``.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _llm_claude import (  # noqa: E402
    LLMError,
    LLMSessionError,
    _build_argv,
    _parse_stream_json,
    _resolve_claude,
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

    # _build_argv: bulk (no effort, no session)
    claude_bin = _resolve_claude()
    argv = _build_argv("claude-sonnet-4-5", None, "")
    assert argv == [claude_bin, "-p", "--output-format", "stream-json", "--verbose",
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

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _llm_claude unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
