"""
LLM-provider wrapper for Claude CLI (`claude -p` subprocess).

This is the lowest layer in the 4-layer review architecture:

    Reviewer -> _llm_claude.run_bulk() / run_tool_use() / run_implementer()
             -> subprocess: claude -p --output-format stream-json ...

Public API:
    LLMError          — raised on timeout, auth failure, or non-zero exit
    LLMSessionError   — subclass raised when --resume <id> fails
    LLMRateLimitError — subclass raised when claude exits non-zero due to rate-limiting
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

When allowed_tools does not include mutating tools (Edit, Write, Bash,
NotebookEdit), _build_argv automatically appends --disallowedTools to deny
those tools at the CLI layer.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

import _subprocess_util
from _llm_common import LLMError, LLMSessionError, LLMRateLimitError


def _claude_argv_prefix() -> list[str]:
    """Return the argv prefix used to invoke the claude CLI.

    On Windows, ``%LOCALAPPDATA%\\Microsoft\\WindowsApps`` (where the npm
    shim ``claude.cmd`` lives) is stripped from the PATH that Python inherits
    in non-interactive subprocess environments such as debugpy or CC's Bash
    tool (see discussion.md § "PATH truncation in debugpy/subprocess
    environments"). Delegating through ``cmd /c`` ensures cmd.exe uses its
    own full interactive PATH, which always includes WindowsApps.

    On POSIX, subprocess inherits the full PATH normally, so the bare name
    suffices.

    Returns:
        ``["cmd", "/c", "claude"]`` on Windows; ``["claude"]`` on POSIX.
    """
    if os.name == "nt":
        return ["cmd", "/c", "claude"]
    return ["claude"]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

# Re-exported from _llm_common — see that module for the class definitions.


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_MUTATING_TOOLS = {"Edit", "Write", "Bash", "NotebookEdit"}
_MODE_BY_ALLOWED_TOOLS: dict[str, str] = {"": "bulk", "Read,Grep,Glob": "tool-use", "Read,Edit,Write,Bash,Grep,Glob,Skill": "implementer"}


def _has_mutating_tool(allowed_tools: str) -> bool:
    """Return True if allowed_tools (comma/whitespace-delimited) contains any mutating tool name."""
    tokens = {t.strip() for t in allowed_tools.replace(",", " ").split() if t.strip()}
    return bool(tokens & _MUTATING_TOOLS)


def _get_via_psmux_flag() -> bool:
    """Check if psmux-based routing is enabled in the mill config.

    Returns False on any error (missing config, parse error, or cwd outside a
    git worktree), so the default direct path is silently used.
    """
    try:
        import _paths
        import _config

        git_root = _paths.resolve_git_root(Path.cwd())
        cfg = _config.load_config(git_root, git_root)
        return bool(cfg.get("llm", {}).get("claude", {}).get("psmux", {}).get("via_psmux", False))
    except (Exception, SystemExit):
        return False


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
        *_claude_argv_prefix(),
        "-p",
        "--output-format", "stream-json",
        "--verbose",  # required by claude CLI when combining -p with stream-json
        "--model", model,
        *(["--allowedTools", allowed_tools] if allowed_tools is not None else []),
    ]
    if not _has_mutating_tool(allowed_tools):
        argv += ["--disallowedTools", "Edit,Write,Bash,NotebookEdit"]
    if effort is not None:
        argv += ["--effort", effort]
    if resume:
        if not session_id:
            raise LLMError("resume=True requires a session_id")
        argv += ["--resume", session_id]
    elif session_id is not None:
        argv += ["--session-id", session_id]
    return argv


def _build_psmux_argv(
    model: str,
    effort: str | None,
    allowed_tools: str,
    session_id: str,
    *,
    psmux_session_name: str | None = None,
    keep_alive: bool = False,
) -> list[str]:
    """Build argv for a psmux subprocess call.

    Args:
        model: Claude model name
        effort: Optional effort level
        allowed_tools: Comma-delimited tool list (used to determine mode)
        session_id: Session ID (always non-None at call site)
        psmux_session_name: Optional psmux session name to use; if None, wrapper
                            falls back to auto-generated 'mill-<uuid8>' name
        keep_alive: If True, pass --keep-alive to wrapper to leave session running
                    on success

    Returns:
        argv list starting with [sys.executable, wrapper_script, ...]

    Raises LLMError if allowed_tools does not map to a known mode.
    """
    mode = _MODE_BY_ALLOWED_TOOLS.get(allowed_tools)
    if mode is None:
        raise LLMError(f"via_psmux: unsupported allowed_tools {allowed_tools!r}")
    wrapper = str(Path(__file__).resolve().parent / "millpy-claude-sub.py")
    argv = [sys.executable, wrapper, "--mode", mode, "--model", model]
    if effort is not None:
        argv += ["--effort", effort]
    argv += ["--session-id", session_id]
    if psmux_session_name is not None:
        argv += ["--psmux-session", psmux_session_name]
    if keep_alive:
        argv += ["--keep-alive"]
    return argv


def _scan_rate_limit(stdout: str) -> bool:
    """Return True if stdout contains a rate-limit/throttle signal.

    Iterates stream-json lines defensively (skips un-parseable lines).
    Returns True when any of:
      (a) top-level type == "rate_limit_event"
      (b) type == "result" AND is_error == True AND (subtype contains "rate"
          case-insensitively, OR the lowercased JSON body contains "rate_limit")
    Returns False for empty stdout, all-good results, or generic errors.
    Does not raise.
    """
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_type = obj.get("type", "")
        if event_type == "rate_limit_event":
            return True
        if event_type == "result" and obj.get("is_error") is True:
            subtype = str(obj.get("subtype", "")).lower()
            if "rate" in subtype:
                return True
            if "rate_limit" in json.dumps(obj).lower():
                return True
    return False


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

    When the subprocess exits non-zero within 2 seconds with empty stdout,
    and resume=False and no rate-limit was detected, the call is retried
    once with the same argv (see issue #153 — cmd /c claude shim flakes
    immediately after a prior session interrupt). The retry's outcome
    propagates as the final result.
    """
    sess_label = f" session={session_id[:8]}..." if session_id else ""
    mode_suffix = "/resume" if resume else ""
    print(
        f"[_llm_claude] claude {model} ({mode_label}{mode_suffix}){sess_label} starting...",
        file=sys.stderr,
    )

    if _get_via_psmux_flag():
        if resume:
            raise LLMError("psmux path does not support session resume; turn off via_psmux for resume flows")
        if shutil.which("psmux") is None:
            raise LLMError("psmux not on PATH; required when llm.claude.via_psmux=true")
        if session_id is None:
            session_id = str(uuid.uuid4())
        start = time.monotonic()
        argv = _build_psmux_argv(model, effort, allowed_tools, session_id)
        try:
            result = _subprocess_util.run(
                argv,
                input=prompt_text,
                timeout=float(timeout),
                cwd=cwd,
            )
        except Exception as exc:
            if "TimeoutExpired" in type(exc).__name__ or "Timeout" in type(exc).__name__:
                raise LLMError(f"psmux-claude timed out after {timeout}s") from exc
            raise LLMError(f"Failed to spawn psmux-claude: {exc}") from exc
        dt = time.monotonic() - start
        if result.returncode != 0:
            error_detail = (result.stderr or result.stdout or "")[:500]
            raise LLMError(f"psmux-claude exited {result.returncode}: {error_detail}")
        text = result.stdout.rstrip()
        sid_log = session_id[:8] if len(session_id) >= 8 else session_id
        print(
            f"[_llm_claude] claude {model} returned {len(text)} chars in {dt:.1f}s"
            f" session={sid_log}",
            file=sys.stderr,
        )
        return text, session_id

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
    rate_limited = _scan_rate_limit(result.stdout or "")
    if (
        result.returncode != 0
        and dt < 2.0
        and not result.stdout.strip()
        and not resume
        and not rate_limited
    ):
        print(
            f"[_llm_claude] fast-fail retry (duration={dt:.2f}s exit={result.returncode})",
            file=sys.stderr,
        )
        result = _subprocess_util.run(argv, input=prompt_text, timeout=float(timeout), cwd=cwd)
        rate_limited = _scan_rate_limit(result.stdout or "")

    if result.returncode != 0:
        error_detail = (result.stderr or result.stdout or "")[:500]
        if rate_limited:
            raise LLMRateLimitError(
                f"claude rate-limited (exit {result.returncode}): {error_detail}"
            )
        if resume:
            raise LLMSessionError(
                f"claude --resume {session_id} exited {result.returncode}: {error_detail}"
            )
        raise LLMError(f"claude exited {result.returncode}: {error_detail}")

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

    Spawns: claude -p --allowedTools Read,Edit,Write,Bash,Grep,Glob,Skill
                   --output-format stream-json
                   --model <model> [--effort <effort>]
                   [--session-id <id> | --resume <id>]

    Tool-set covers file I/O, shell commands, codebase navigation, and
    skill invocation. ``Skill`` is included so the implementer can invoke
    ``@git-commit`` (per implementer-brief.md) and any other skills the
    brief instructs. WebFetch/WebSearch are deliberately absent; TodoWrite
    can be added later if session-local progress tracking is desired.

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
        allowed_tools="Read,Edit,Write,Bash,Grep,Glob,Skill",
        mode_label="implementer",
        timeout=timeout,
        session_id=session_id,
        resume=resume,
        cwd=cwd,
    )


# ---------------------------------------------------------------------------
# Self-test (smoke tests)
# ---------------------------------------------------------------------------
