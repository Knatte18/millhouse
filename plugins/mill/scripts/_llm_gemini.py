"""
LLM-provider wrapper for the `gemini` CLI (`gemini -p` subprocess).

This is the lowest layer in the 4-layer review architecture:

    Reviewer -> _llm_gemini.run_bulk() / run_tool_use()
             -> subprocess: gemini -p -o stream-json ...

Mirrors `_llm_claude.py`'s public surface minus `run_implementer`, which is
out of scope for the Gemini provider (see discussion.md § "Scope (Out)").

Public API:
    LLMError          — raised on timeout, auth failure, or non-zero exit
    LLMSessionError   — subclass raised immediately when resume=True (not supported)
    LLMRateLimitError — subclass raised when gemini exits non-zero with rate-limit signal
    run_bulk()        — invoke gemini in read-only mode; return (text, session_id)
    run_tool_use()    — invoke gemini with default extensions; return (text, session_id)
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid

import _subprocess_util

from _llm_common import LLMError, LLMSessionError, LLMRateLimitError


def _gemini_argv_prefix() -> list[str]:
    """Return the argv prefix used to invoke the gemini CLI.

    On Windows, npm shims such as ``gemini.cmd`` live in
    ``%LOCALAPPDATA%\\Microsoft\\WindowsApps`` and at
    ``C:\\Code\\tools\\bin\\gemini.CMD``. These directories are frequently
    absent from the truncated PATH that Python inherits in non-interactive
    subprocess environments such as debugpy or CC's Bash tool (see
    ``_claude_argv_prefix``'s docstring for the canonical explanation of the
    PATH-truncation rationale — the same logic applies here). Delegating
    through ``cmd /c`` ensures cmd.exe uses its own full interactive PATH.

    On POSIX, subprocess inherits the full PATH normally, so the bare name
    suffices.

    Returns:
        ``["cmd", "/c", "gemini"]`` on Windows; ``["gemini"]`` on POSIX.
    """
    if os.name == "nt":
        return ["cmd", "/c", "gemini"]
    return ["gemini"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_argv(model: str, *, tooluse: bool) -> list[str]:
    """Build the full argv for a ``gemini -p`` subprocess call.

    Args:
        model:   The Gemini model name (e.g. ``"gemini-2.5-flash"``).
        tooluse: When True, the agent runs with default extensions (file
                 inspection allowed; writes denied by the policy layer).
                 When False, ``-e ""`` is appended to disable extensions so
                 gemini runs in read-only bulk mode.

    No ``--effort``, ``--session-id``, or ``--resume`` flags are emitted here.
    ``effort`` is ignored (gemini-cli exposes no thinking-budget flag in
    headless mode); session reuse is short-circuited before this function is
    reached (``session-reuse-not-supported``).
    """
    argv = [
        *_gemini_argv_prefix(),
        "-p", "",  # empty value triggers headless mode; actual prompt arrives via stdin
        "-o", "stream-json",
        "-m", model,
        "--approval-mode", "plan",
    ]
    if not tooluse:
        argv += ["-e", ""]
    return argv


def _scan_gemini_rate_limit(stdout: str, stderr: str) -> bool:
    """Return True if stdout or stderr contains a rate-limit/quota signal.

    Combines stdout and stderr, lowercases once, then returns True when any
    of the following substrings is present:
      ``resource_exhausted``, ``rate_limit``, ``rate limit``, ``quota``,
      ``429``, ``too many requests``.

    Operates on raw text — does NOT iterate stream-JSON lines — so it
    tolerates schema drift. Empty inputs return False. Does not raise.
    """
    combined = f"{stdout}\n{stderr}".lower()
    signals = [
        "resource_exhausted",
        "rate_limit",
        "rate limit",
        "quota",
        "429",
        "too many requests",
    ]
    return any(s in combined for s in signals)


def _parse_gemini_stream_json(stdout: str) -> tuple[str, str | None]:
    """Parse gemini's stream-json output.

    Returns ``(final_text, session_id)``. ``session_id`` is extracted from any
    top-level ``session_id`` field (last-wins). Final text is taken from (in
    priority order, last-wins): a ``"message"`` event with ``role == "assistant"``
    and a non-empty ``content`` string or list; a ``"result"`` event with a
    non-empty ``result`` string (legacy CLI format); or a ``"assistant"`` event
    with a nested ``message.content`` list (legacy format).

    Stream-json emits one JSON object per line. Lines that fail JSON parsing
    emit a stderr warning and are skipped.

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
                f"[_llm_gemini] warning: could not parse stream-json line: {exc}",
                file=sys.stderr,
            )
            continue

        sid = obj.get("session_id")
        if isinstance(sid, str) and sid:
            session_id = sid

        event_type = obj.get("type", "")
        if event_type == "message" and obj.get("role") == "assistant":
            # Current gemini CLI emits assistant text here (content is a plain string).
            content = obj.get("content", "")
            if isinstance(content, str) and content.strip():
                final_text = content
            elif isinstance(content, list):
                parts = [
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                combined = "".join(parts)
                if combined.strip():
                    final_text = combined
        elif event_type == "result":
            # Older CLI versions emitted text in "result"; current versions use "message".
            result_value = obj.get("result", "")
            if isinstance(result_value, str) and result_value.strip():
                final_text = result_value
        elif event_type == "assistant":
            # Legacy format where type itself is "assistant" with nested message object.
            message = obj.get("message", {})
            content = message.get("content", [])
            if isinstance(content, list):
                parts = [
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                combined = "".join(parts)
                if combined.strip():
                    final_text = combined

    if final_text is None:
        raise LLMError("gemini returned no content")
    return final_text, session_id


def _invoke(
    prompt_text: str,
    model: str,
    mode_label: str,
    timeout: int,
    *,
    tooluse: bool,
    session_id: str | None = None,
    resume: bool = False,
) -> tuple[str, str]:
    """Core invocation: spawn gemini, parse output, return (text, session_id).

    Raises LLMSessionError immediately when ``resume=True`` — gemini-cli does
    not support session resumption. Raises LLMError on timeout or non-zero
    exit. Raises LLMRateLimitError when the exit is non-zero AND rate-limit
    signals are detected in the output.
    """
    if resume:
        raise LLMSessionError("gemini session reuse not supported")

    print(f"[_llm_gemini] gemini {model} ({mode_label}) starting...", file=sys.stderr)

    argv = _build_argv(model, tooluse=tooluse)
    start = time.monotonic()

    try:
        result = _subprocess_util.run(argv, input=prompt_text, timeout=float(timeout))
    except Exception as exc:
        if "TimeoutExpired" in type(exc).__name__ or "Timeout" in type(exc).__name__:
            raise LLMError(f"Gemini CLI timed out after {timeout}s") from exc
        raise LLMError(f"Failed to spawn gemini: {exc}") from exc

    dt = time.monotonic() - start
    rate_limited = _scan_gemini_rate_limit(result.stdout or "", result.stderr or "")

    if result.returncode != 0:
        error_detail = (result.stderr or result.stdout or "")[:500]
        if rate_limited:
            raise LLMRateLimitError(
                f"gemini rate-limited (exit {result.returncode}): {error_detail}"
            )
        raise LLMError(f"gemini exited {result.returncode}: {error_detail}")

    text, observed_sid = _parse_gemini_stream_json(result.stdout or "")
    effective_sid = observed_sid or f"gemini-{uuid.uuid4()}"
    print(
        f"[_llm_gemini] gemini {model} returned {len(text)} chars in {dt:.1f}s"
        f" session={effective_sid[:8]}",
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
    """Invoke gemini with no extensions in read-only mode (bulk mode).

    Spawns: gemini -p -o stream-json -m <model> --approval-mode plan -e ""

    Stdin receives prompt_text. Stream-json is parsed; the final assistant
    text and session_id are returned as a tuple.

    ``effort`` is accepted for API parity with ``_llm_claude.run_bulk`` but is
    silently ignored — gemini-cli exposes no thinking-budget flag in headless
    mode.

    ``session_id`` is accepted but ignored on fresh calls; gemini-cli does not
    support session-id injection.

    Raises LLMSessionError immediately when ``resume=True`` — gemini session
    reuse is not supported.
    Raises LLMError on timeout, non-zero exit, or empty response.
    Raises LLMRateLimitError on rate-limit signals with non-zero exit.
    """
    return _invoke(
        prompt_text=prompt_text,
        model=model,
        mode_label="bulk",
        timeout=timeout,
        tooluse=False,
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
    """Invoke gemini with default extensions in read-only mode (tool-use mode).

    Spawns: gemini -p -o stream-json -m <model> --approval-mode plan

    File inspection is allowed; writes are denied by the policy layer
    (``--approval-mode plan`` requires human approval for any file writes).

    ``effort`` is accepted for API parity with ``_llm_claude.run_tool_use``
    but is silently ignored — gemini-cli exposes no thinking-budget flag in
    headless mode.

    ``session_id`` is accepted but ignored on fresh calls; gemini-cli does not
    support session-id injection.

    Raises LLMSessionError immediately when ``resume=True`` — gemini session
    reuse is not supported.
    Raises LLMError on timeout, non-zero exit, or empty response.
    Raises LLMRateLimitError on rate-limit signals with non-zero exit.
    """
    return _invoke(
        prompt_text=prompt_text,
        model=model,
        mode_label="tool-use",
        timeout=timeout,
        tooluse=True,
        session_id=session_id,
        resume=resume,
    )
