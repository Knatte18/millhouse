"""
LLM-provider wrapper for Claude CLI (`claude -p` subprocess).

This is the lowest layer in the 4-layer review architecture:

    Reviewer -> _llm_claude.run_bulk() / run_tool_use() / run_implementer()
             -> subprocess: claude -p --output-format stream-json ...

Public API:
    LLMError          — raised on timeout, auth failure, or non-zero exit
    LLMSessionError   — subclass raised when --resume <id> fails
    run_bulk()        — invoke claude with no tools; return (text, session_id)
    run_tool_use()    — invoke claude with Read/Grep/Glob; return (text, session_id)
    run_implementer() — invoke claude with Read/Edit/Write/Bash/Grep/Glob;
                        return (text, session_id). For mill-go's per-batch worker.

All three accept optional `session_id` and `resume` parameters so callers can
reuse a warm Claude session across turns (implement → review → fix) without
re-loading context each time. Callers that don't care about session reuse
simply ignore the returned session_id.

The prompt is sent on stdin; stream-json output is parsed to extract the
final assistant text and the session_id. Stderr receives one-line progress
messages on entry and exit.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

import _subprocess_util


def _resolve_claude() -> str:
    """Return the absolute path to the claude CLI, or the bare name as fallback.

    On Windows, `claude` is typically installed as `claude.cmd` (an npm shim).
    Python's subprocess.run does not resolve `.cmd`/`.bat` extensions without
    shell=True, so we look up the full resolved path via shutil.which and
    pass it to subprocess. shutil.which understands PATHEXT on Windows and
    finds `claude.cmd` or `claude.exe` as appropriate.
    """
    resolved = shutil.which("claude")
    if resolved is None:
        # Let subprocess raise its own "file not found" error downstream;
        # returning the bare name here keeps the error path unchanged.
        return "claude"
    return resolved


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """Raised on timeout, auth failure, or non-zero exit from claude CLI.

    Callers use str(exc) to get a human-readable error message. Backends
    catch LLMError at the per-sub-review boundary and record
    {verdict: "ERROR", file: null, error: "<msg>"} in the ReviewResult.
    """


class LLMSessionError(LLMError):
    """Raised when `claude -p --resume <id>` fails because the session is gone.

    Callers (mill-go's builder) catch this specifically to fall back to a
    fresh session instead of aborting the batch.
    """


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_argv(
    model: str,
    effort: str | None,
    allowed_tools: str,
    session_id: str | None = None,
    resume: bool = False,
) -> list[str]:
    """Build the base argv for a `claude -p` subprocess call.

    Session handling:
      * resume=True               -> --resume <session_id>  (id required)
      * session_id set, resume F  -> --session-id <session_id>  (new session, chosen id)
      * both unset                -> no flags; claude assigns an id server-side
    """
    argv = [
        _resolve_claude(),
        "-p",
        "--output-format", "stream-json",
        "--verbose",  # required by claude CLI when combining -p with stream-json
        "--model", model,
        "--allowedTools", allowed_tools,
    ]
    if effort is not None:
        argv += ["--effort", effort]
    if resume:
        if not session_id:
            raise LLMError("resume=True requires a session_id")
        argv += ["--resume", session_id]
    elif session_id is not None:
        argv += ["--session-id", session_id]
    return argv


def _parse_stream_json(stdout: str) -> tuple[str, str | None]:
    """Parse claude's stream-json output.

    Returns (final_text, session_id). session_id is extracted from any event
    that carries a top-level `session_id` field (the init "system" event
    always does; the final "result" event typically does too). The last one
    seen wins.

    Stream-json emits one JSON object per line. Lines that fail JSON
    parsing emit a stderr warning and are skipped.

    Raises LLMError if no assistant text is found after consuming all lines.
    """
    final_text: str | None = None
    session_id: str | None = None

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            print(
                f"[_llm_claude] warning: could not parse stream-json line: {exc}",
                file=sys.stderr,
            )
            continue

        # session_id is top-level on most event types (init, result, assistant).
        sid = obj.get("session_id")
        if isinstance(sid, str) and sid:
            session_id = sid

        # stream-json event types vary by claude CLI version. We accept:
        #   {"type": "result", "result": "<text>"}
        # and fall back to scanning for any string value in "result" or
        # top-level "content" / "text" fields in case the schema evolves.
        event_type = obj.get("type", "")
        if event_type == "result":
            result_value = obj.get("result", "")
            if isinstance(result_value, str) and result_value.strip():
                final_text = result_value
        elif event_type == "assistant":
            # Some versions emit {"type":"assistant","message":{"content":[...]}}
            message = obj.get("message", {})
            content = message.get("content", [])
            if isinstance(content, list):
                parts = [
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                combined = "".join(parts).strip()
                if combined:
                    final_text = combined

    if final_text is None:
        raise LLMError("claude returned no content")
    return final_text, session_id


def _invoke(
    prompt_text: str,
    model: str,
    effort: str | None,
    allowed_tools: str,
    mode_label: str,
    timeout: int,
    session_id: str | None = None,
    resume: bool = False,
    cwd: Path | str | None = None,
) -> tuple[str, str]:
    """Core invocation: spawn claude, parse output, return (text, session_id).

    Raises LLMError on failure. When resume=True and the subprocess exits
    non-zero, raises LLMSessionError instead so callers can distinguish a
    dead-session fallback path from a generic failure.
    """
    sess_label = f" session={session_id[:8]}..." if session_id else ""
    mode_suffix = "/resume" if resume else ""
    print(
        f"[_llm_claude] claude {model} ({mode_label}{mode_suffix}){sess_label} starting...",
        file=sys.stderr,
    )
    start = time.monotonic()
    argv = _build_argv(model, effort, allowed_tools, session_id, resume)

    try:
        result = _subprocess_util.run(
            argv,
            input=prompt_text,
            timeout=float(timeout),
            cwd=cwd,
        )
    except Exception as exc:  # subprocess.TimeoutExpired or similar
        if "TimeoutExpired" in type(exc).__name__ or "Timeout" in type(exc).__name__:
            raise LLMError(f"Claude CLI timed out after {timeout}s") from exc
        raise LLMError(f"Failed to spawn claude: {exc}") from exc

    dt = time.monotonic() - start

    if result.returncode != 0:
        stderr_snippet = (result.stderr or "")[:500]
        if resume:
            raise LLMSessionError(
                f"claude --resume {session_id} exited {result.returncode}: {stderr_snippet}"
            )
        raise LLMError(f"claude exited {result.returncode}: {stderr_snippet}")

    text, observed_sid = _parse_stream_json(result.stdout)
    effective_sid = observed_sid or session_id
    if not effective_sid:
        raise LLMError("claude CLI did not emit a session_id in stream-json output")
    sid_log = effective_sid[:8] if len(effective_sid) >= 8 else effective_sid
    print(
        f"[_llm_claude] claude {model} returned {len(text)} chars in {dt:.1f}s"
        f" session={sid_log}",
        file=sys.stderr,
    )
    return text, effective_sid


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_bulk(
    prompt_text: str,
    *,
    model: str,
    effort: str | None = None,
    timeout: int = 600,
    session_id: str | None = None,
    resume: bool = False,
) -> tuple[str, str]:
    """Invoke claude with no tool access (bulk mode).

    Spawns: claude -p --allowedTools "" --output-format stream-json
                   --model <model> [--effort <effort>]
                   [--session-id <id> | --resume <id>]

    Stdin receives prompt_text. Stream-json is parsed; the final assistant
    text and session_id are returned as a tuple.

    Raises LLMError on timeout, non-zero exit, or empty response.
    Raises LLMSessionError when resume=True and the subprocess fails.
    """
    return _invoke(
        prompt_text=prompt_text,
        model=model,
        effort=effort,
        allowed_tools="",
        mode_label="bulk",
        timeout=timeout,
        session_id=session_id,
        resume=resume,
    )


def run_tool_use(
    prompt_text: str,
    *,
    model: str,
    effort: str | None = None,
    timeout: int = 900,
    session_id: str | None = None,
    resume: bool = False,
) -> tuple[str, str]:
    """Invoke claude with read-only tool access (tool-use mode).

    Spawns: claude -p --allowedTools Read,Grep,Glob --output-format stream-json
                   --model <model> [--effort <effort>]
                   [--session-id <id> | --resume <id>]

    Write/Edit/Bash are intentionally excluded: the backend always writes the
    review file after the reviewer returns (Decision 24 in discussion.md).
    Glob is included to aid file discovery. Longer default timeout (900s)
    for sessions that explore the codebase.

    Raises LLMError on timeout, non-zero exit, or empty response.
    Raises LLMSessionError when resume=True and the subprocess fails.
    """
    return _invoke(
        prompt_text=prompt_text,
        model=model,
        effort=effort,
        allowed_tools="Read,Grep,Glob",
        mode_label="tool-use",
        timeout=timeout,
        session_id=session_id,
        resume=resume,
    )


def run_implementer(
    prompt_text: str,
    *,
    model: str,
    effort: str | None = None,
    timeout: int = 1800,
    session_id: str | None = None,
    resume: bool = False,
    cwd: Path | str | None = None,
) -> tuple[str, str]:
    """Invoke claude as mill-go's per-batch implementer.

    Spawns: claude -p --allowedTools Read,Edit,Write,Bash,Grep,Glob
                   --output-format stream-json
                   --model <model> [--effort <effort>]
                   [--session-id <id> | --resume <id>]

    Tool-set is the minimum needed for the implementer to read the plan,
    edit files, run `verify:` commands via Bash, and navigate the
    codebase. WebFetch/WebSearch are deliberately absent; TodoWrite can be
    added later if session-local progress tracking is desired.

    `cwd` is passed to the subprocess (typically the worktree root) so
    Bash calls run in the right directory.

    Default timeout is 1800s (30 min) — batches can take a while when
    verify commands run tests. Callers reading wiki config should prefer
    `llm.implementer_timeout` over the code default.

    Raises LLMError on timeout, non-zero exit, or empty response.
    Raises LLMSessionError when resume=True and the subprocess fails.
    """
    return _invoke(
        prompt_text=prompt_text,
        model=model,
        effort=effort,
        allowed_tools="Read,Edit,Write,Bash,Grep,Glob",
        mode_label="implementer",
        timeout=timeout,
        session_id=session_id,
        resume=resume,
        cwd=cwd,
    )


# ---------------------------------------------------------------------------
# Self-test (smoke tests)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import shutil

    print("Running _llm_claude.py smoke tests...", file=sys.stderr)
    errors = 0

    # --- Module imports cleanly and public symbols exist ---
    assert callable(run_bulk), "run_bulk must be callable"
    assert callable(run_tool_use), "run_tool_use must be callable"
    assert callable(run_implementer), "run_implementer must be callable"
    assert issubclass(LLMError, Exception), "LLMError must be an Exception subclass"
    assert issubclass(LLMSessionError, LLMError), "LLMSessionError must subclass LLMError"
    print("PASS: module imports cleanly, public symbols present")

    # --- Function signatures (keyword-only model arg, session_id/resume present) ---
    import inspect
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
    # cwd only on run_implementer
    assert "cwd" in inspect.signature(run_implementer).parameters
    assert "cwd" not in inspect.signature(run_bulk).parameters
    print("PASS: signatures have session_id/resume (cwd only on run_implementer)")

    # --- LLMError and LLMSessionError behave as expected ---
    try:
        raise LLMError("test error")
    except LLMError as e:
        assert str(e) == "test error"
        print("PASS: LLMError raises and str() works")
    except Exception:
        print("FAIL: LLMError not caught as LLMError", file=sys.stderr)
        errors += 1

    try:
        raise LLMSessionError("stale session")
    except LLMError as e:  # subclass should be caught as base
        assert str(e) == "stale session"
        print("PASS: LLMSessionError is caught as LLMError")
    except Exception:
        print("FAIL: LLMSessionError not caught as LLMError", file=sys.stderr)
        errors += 1

    # --- _parse_stream_json: valid result event with session_id ---
    raw = (
        '{"type":"system","subtype":"init","session_id":"abc123"}\n'
        '{"type":"result","result":"APPROVE\\n\\nLooks good.","session_id":"abc123"}\n'
    )
    text, sid = _parse_stream_json(raw)
    assert "APPROVE" in text, f"Expected APPROVE in: {text!r}"
    assert sid == "abc123", f"Expected session_id 'abc123', got {sid!r}"
    print("PASS: _parse_stream_json extracts result text + session_id")

    # --- _parse_stream_json: session_id from init only (no result sid) ---
    raw = (
        '{"type":"system","subtype":"init","session_id":"init-only"}\n'
        '{"type":"result","result":"OK"}\n'
    )
    text, sid = _parse_stream_json(raw)
    assert text == "OK" and sid == "init-only"
    print("PASS: _parse_stream_json falls back to init session_id")

    # --- _parse_stream_json: no session_id at all (returns None) ---
    text, sid = _parse_stream_json('{"type":"result","result":"OK"}\n')
    assert text == "OK" and sid is None
    print("PASS: _parse_stream_json returns None session_id when absent")

    # --- _parse_stream_json: no content -> LLMError ---
    try:
        _parse_stream_json('{"type":"other","data":"x"}\n')
        print("FAIL: expected LLMError for empty content", file=sys.stderr)
        errors += 1
    except LLMError:
        print("PASS: _parse_stream_json no content -> LLMError")

    # --- _parse_stream_json: bad JSON line is skipped ---
    mixed = 'not-json\n{"type":"result","result":"OK","session_id":"s1"}\n'
    text, sid = _parse_stream_json(mixed)
    assert text == "OK" and sid == "s1"
    print("PASS: _parse_stream_json skips bad JSON line")

    # --- _build_argv: bulk (no effort, no session) ---
    argv = _build_argv("claude-sonnet-4-5", None, "")
    claude_bin = _resolve_claude()
    assert argv == [claude_bin, "-p", "--output-format", "stream-json", "--verbose",
                    "--model", "claude-sonnet-4-5", "--allowedTools", ""]
    print("PASS: _build_argv bulk without effort / without session")

    # --- _build_argv: tool-use with effort ---
    argv = _build_argv("claude-sonnet-4-5", "max", "Read,Grep,Glob")
    assert "--effort" in argv and "max" in argv
    assert "Read,Grep,Glob" in argv
    print("PASS: _build_argv tool-use with effort")

    # --- _build_argv: --session-id when session given, resume=False ---
    argv = _build_argv("claude-sonnet-4-5", None, "", session_id="my-uuid", resume=False)
    assert "--session-id" in argv and "my-uuid" in argv
    assert "--resume" not in argv
    print("PASS: _build_argv emits --session-id for new session with chosen id")

    # --- _build_argv: --resume when resume=True ---
    argv = _build_argv("claude-sonnet-4-5", None, "", session_id="my-uuid", resume=True)
    assert "--resume" in argv and "my-uuid" in argv
    assert "--session-id" not in argv
    print("PASS: _build_argv emits --resume when resume=True")

    # --- _build_argv: resume=True without session_id -> LLMError ---
    try:
        _build_argv("claude-sonnet-4-5", None, "", session_id=None, resume=True)
        print("FAIL: expected LLMError for resume without session_id", file=sys.stderr)
        errors += 1
    except LLMError:
        print("PASS: _build_argv rejects resume=True without session_id")

    # --- run_implementer has the expanded tool-set in its argv construction ---
    # (indirect: inspect the allowed_tools constant path via code search would
    # be overkill; trust the source.)

    # --- Skip live-claude test if not in PATH ---
    if shutil.which("claude") is None:
        print("SKIP: claude not in PATH -- live invocation tests skipped", file=sys.stderr)
    else:
        print("INFO: claude found in PATH; live tests would run in smoke-llm-claude.py", file=sys.stderr)

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        sys.exit(1)
    else:
        print("\nAll smoke tests passed.")
