"""
LLM-provider wrapper for Claude CLI (`claude -p` subprocess).

This is the lowest layer in the 4-layer review architecture:

    Reviewer -> _llm_claude.run_bulk() / run_tool_use()
             -> subprocess: claude -p --output-format stream-json ...

Public API:
    LLMError       — raised on timeout, auth failure, or non-zero exit
    run_bulk()     — invoke claude with no tools; return final text
    run_tool_use() — invoke claude with Read/Grep/Glob; return final text

Both functions accept the prompt on stdin and parse stream-json output to
extract the final assistant text. They raise LLMError on any subprocess
failure; they do not catch LLMError themselves.

Stderr receives one-line progress messages on entry and exit.
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
# Exception
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """Raised on timeout, auth failure, or non-zero exit from claude CLI.

    Callers use str(exc) to get a human-readable error message. Backends
    catch LLMError at the per-sub-review boundary and record
    {verdict: "ERROR", file: null, error: "<msg>"} in the ReviewResult.
    """


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_argv(
    model: str,
    effort: str | None,
    allowed_tools: str,
) -> list[str]:
    """Build the base argv for a `claude -p` subprocess call."""
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
    return argv


def _parse_stream_json(stdout: str) -> str:
    """Parse claude's stream-json output and return the final assistant text.

    Stream-json emits one JSON object per line. We look for the last line
    that is a `result` event with a non-empty `result` field (the final
    response text). Lines that fail JSON parsing emit a stderr warning and
    are skipped.

    Raises LLMError if no assistant text is found after consuming all lines.
    """
    final_text: str | None = None

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
    return final_text


def _invoke(
    prompt_text: str,
    model: str,
    effort: str | None,
    allowed_tools: str,
    mode_label: str,
    timeout: int,
) -> str:
    """Core invocation: spawn claude, parse output, return text or raise LLMError."""
    print(
        f"[_llm_claude] claude {model} ({mode_label}) starting...",
        file=sys.stderr,
    )
    start = time.monotonic()
    argv = _build_argv(model, effort, allowed_tools)

    try:
        result = _subprocess_util.run(
            argv,
            input=prompt_text,
            timeout=float(timeout),
        )
    except Exception as exc:  # subprocess.TimeoutExpired or similar
        if "TimeoutExpired" in type(exc).__name__ or "Timeout" in type(exc).__name__:
            raise LLMError(f"Claude CLI timed out after {timeout}s") from exc
        raise LLMError(f"Failed to spawn claude: {exc}") from exc

    dt = time.monotonic() - start

    if result.returncode != 0:
        stderr_snippet = (result.stderr or "")[:500]
        raise LLMError(f"claude exited {result.returncode}: {stderr_snippet}")

    text = _parse_stream_json(result.stdout)
    print(
        f"[_llm_claude] claude {model} returned {len(text)} chars in {dt:.1f}s",
        file=sys.stderr,
    )
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_bulk(
    prompt_text: str,
    *,
    model: str,
    effort: str | None = None,
    timeout: int = 600,
) -> str:
    """Invoke claude with no tool access (bulk mode).

    Spawns: claude -p --allowedTools "" --output-format stream-json
                   --model <model> [--effort <effort>]

    Stdin receives prompt_text. Stream-json is parsed; the final assistant
    text is returned.

    Raises LLMError on timeout, non-zero exit, or empty response.
    """
    return _invoke(
        prompt_text=prompt_text,
        model=model,
        effort=effort,
        allowed_tools="",
        mode_label="bulk",
        timeout=timeout,
    )


def run_tool_use(
    prompt_text: str,
    *,
    model: str,
    effort: str | None = None,
    timeout: int = 900,
) -> str:
    """Invoke claude with read-only tool access (tool-use mode).

    Spawns: claude -p --allowedTools Read,Grep,Glob --output-format stream-json
                   --model <model> [--effort <effort>]

    Write is intentionally excluded: the backend always writes the review
    file after the reviewer returns (Decision 24 in discussion.md). Glob is
    included to aid file discovery. Longer default timeout (900s) for
    sessions that explore the codebase.

    Raises LLMError on timeout, non-zero exit, or empty response.
    """
    return _invoke(
        prompt_text=prompt_text,
        model=model,
        effort=effort,
        allowed_tools="Read,Grep,Glob",
        mode_label="tool-use",
        timeout=timeout,
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
    assert issubclass(LLMError, Exception), "LLMError must be an Exception subclass"
    print("PASS: module imports cleanly, public symbols present")

    # --- Function signatures (keyword-only model arg) ---
    import inspect
    sig_bulk = inspect.signature(run_bulk)
    sig_tool = inspect.signature(run_tool_use)
    assert "prompt_text" in sig_bulk.parameters
    assert "model" in sig_bulk.parameters
    assert "effort" in sig_bulk.parameters
    assert "timeout" in sig_bulk.parameters
    assert sig_bulk.parameters["model"].kind == inspect.Parameter.KEYWORD_ONLY
    assert "prompt_text" in sig_tool.parameters
    assert "model" in sig_tool.parameters
    print("PASS: run_bulk and run_tool_use have correct signatures")

    # --- LLMError is a plain Exception subclass ---
    try:
        raise LLMError("test error")
    except LLMError as e:
        assert str(e) == "test error"
        print("PASS: LLMError raises and str() works")
    except Exception:
        print("FAIL: LLMError not caught as LLMError", file=sys.stderr)
        errors += 1

    # --- _parse_stream_json: valid result event ---
    raw = '{"type":"result","result":"APPROVE\\n\\nLooks good."}\n'
    text = _parse_stream_json(raw)
    assert "APPROVE" in text, f"Expected APPROVE in: {text!r}"
    print("PASS: _parse_stream_json extracts result text")

    # --- _parse_stream_json: no content -> LLMError ---
    try:
        _parse_stream_json('{"type":"other","data":"x"}\n')
        print("FAIL: expected LLMError for empty content", file=sys.stderr)
        errors += 1
    except LLMError:
        print("PASS: _parse_stream_json no content -> LLMError")

    # --- _parse_stream_json: bad JSON line is skipped ---
    mixed = 'not-json\n{"type":"result","result":"OK"}\n'
    text = _parse_stream_json(mixed)
    assert text == "OK", f"Expected 'OK', got {text!r}"
    print("PASS: _parse_stream_json skips bad JSON line")

    # --- _build_argv: bulk (no effort) ---
    argv = _build_argv("claude-sonnet-4-5", None, "")
    assert argv == ["claude", "-p", "--output-format", "stream-json",
                    "--model", "claude-sonnet-4-5", "--allowedTools", ""]
    print("PASS: _build_argv bulk without effort")

    # --- _build_argv: tool-use with effort ---
    argv = _build_argv("claude-sonnet-4-5", "max", "Read,Grep,Glob")
    assert "--effort" in argv and "max" in argv
    assert "Read,Grep,Glob" in argv
    print("PASS: _build_argv tool-use with effort")

    # --- Skip live-claude test if not in PATH ---
    if shutil.which("claude") is None:
        print("SKIP: claude not in PATH -- live invocation tests skipped", file=sys.stderr)
    else:
        print("INFO: claude found in PATH; live tests would run here", file=sys.stderr)

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        sys.exit(1)
    else:
        print("\nAll smoke tests passed.")
