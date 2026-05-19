"""
Drop-in replacement for `claude -p` that routes through interactive `claude` via psmux
for subscription billing instead of API credits. Accepts prompt on stdin, returns Claude's
response on stdout, emits one-line JSON metadata `{session_id, duration_s, mode}` on stderr.

Four modes with hardcoded tool sets per Shared Decision in discussion.md: `bulk`
(--tools ""), `tool-use` (--allowedTools "Read,Grep,Glob"), `implementer`
(--allowedTools "Read,Edit,Write,Bash,Grep,Glob,Skill"). See _psmux.py (driver)
and _psmux_capture.py (parser) for the psmux automation and response extraction.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
import time
import uuid

import _config
import _paths
import _psmux
import _psmux_capture

# Boot and polling constants
BOOT_READY_TIMEOUT_S = 60
PSMUX_COMMAND_TIMEOUT_S = 30  # Synchronized with _psmux.py; keep in sync
POLL_INTERVAL_S = 1.0
REUSE_IDLE_TIMEOUT_S_DEFAULT = 10
RESPONSE_POLL_TIMEOUT_S: dict[str, int] = {
    "bulk": 300,
    "tool-use": 600,
    "implementer": 1800,
}

# Mode-implicit tool sets
MODE_TOOL_FLAGS: dict[str, list[str]] = {
    "bulk": ["--tools", ""],
    "tool-use": ["--allowedTools", "Read,Grep,Glob"],
    "implementer": ["--allowedTools", "Read,Edit,Write,Bash,Grep,Glob,Skill"],
}


def _ps_join(args: list[str]) -> str:
    """Build a PowerShell-compatible command string. Differs from shlex.join for empty strings:
    shlex emits '' (POSIX) but cmd.exe drops empty-string args when expanding %*; use "" instead."""
    result = []
    for arg in args:
        if arg == "":
            result.append('""')
        elif re.search(r'[\s"\'`]', arg):
            result.append('"' + arg.replace('"', '`"') + '"')
        else:
            result.append(arg)
    return " ".join(result)


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Drop-in replacement for 'claude -p' using subscription billing via psmux"
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["bulk", "tool-use", "implementer"],
        help="Mode determines tool set: bulk (no tools), tool-use (Read/Grep/Glob), implementer (all)",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Claude model name (e.g. claude-opus-4-1)",
    )
    parser.add_argument(
        "--effort",
        choices=["low", "medium", "high", "xhigh", "max"],
        help="Optional effort level passed to claude",
    )
    parser.add_argument(
        "--session-id",
        default=str(uuid.uuid4()),
        help="Session ID (default: generated UUID)",
    )
    parser.add_argument(
        "--psmux-session",
        default=None,
        help="Reuse the named psmux session if it exists; create it under this name if not. Default: auto-generated 'mill-<uuid8>'.",
    )
    parser.add_argument(
        "--keep-alive",
        action="store_true",
        help="On success, leave the psmux session running for reuse by a later call.",
    )
    return parser


def _wait_for_marker_in_pane(
    session_name: str, marker: str, timeout_s: float
) -> bool:
    """Poll capture-pane for a line containing marker. Return True on match, False on timeout."""
    start = time.monotonic()
    while True:
        try:
            capture = _psmux.capture_pane(session_name)
            for line in capture.splitlines():
                if marker in line.strip():
                    return True
        except _psmux.PsmuxError:
            return False

        if time.monotonic() - start >= timeout_s:
            return False
        time.sleep(POLL_INTERVAL_S)


def _wait_for_idle_prompt(session_name: str, timeout_s: float) -> bool:
    """Poll capture-pane for the idle prompt character. Return True on match, False on timeout."""
    idle_prompt = "❯"
    start = time.monotonic()
    while True:
        try:
            capture = _psmux.capture_pane(session_name, alternate=True)
            for line in capture.splitlines():
                if line.strip().startswith(idle_prompt):
                    return True
        except _psmux.PsmuxError:
            return False

        if time.monotonic() - start >= timeout_s:
            return False
        time.sleep(POLL_INTERVAL_S)


def _resolve_reuse_idle_timeout_s() -> float:
    """Load reuse_idle_timeout_s from config, defaulting to REUSE_IDLE_TIMEOUT_S_DEFAULT."""
    try:
        git_root = _paths.resolve_git_root()
        cfg = _config.load_config(git_root, git_root)
        return float(
            cfg.get("llm", {})
            .get("claude", {})
            .get("psmux", {})
            .get("reuse_idle_timeout_s", REUSE_IDLE_TIMEOUT_S_DEFAULT)
        )
    except (Exception, SystemExit):
        return float(REUSE_IDLE_TIMEOUT_S_DEFAULT)


def main() -> int:
    parser = _make_parser()
    args = parser.parse_args()

    # Step 1: Read prompt from stdin
    prompt_body = sys.stdin.read()
    if not prompt_body:
        print("[millpy-claude-sub] empty prompt on stdin", file=sys.stderr)
        return 2

    # Step 2: Generate session name and markers
    session_name = args.psmux_session if args.psmux_session is not None else f"mill-{uuid.uuid4().hex[:8]}"
    begin_marker = f"MILL_BEGIN_{secrets.token_hex(4)}"
    end_marker = f"MILL_END_{secrets.token_hex(4)}"

    # Step 3: Append dual-marker footer to prompt
    footer = f"""Reply protocol (mandatory): begin your reply with the literal text
{begin_marker} on its own line, end your reply with the literal
text {end_marker} on its own line. Do not include either token
anywhere else in your reply."""
    full_prompt = prompt_body + "\n\n" + footer

    # Step 4: Resolve scratch dir and write prompt file
    scratch_dir = _paths.resolve_git_root() / ".scratch"
    scratch_dir.mkdir(exist_ok=True)
    prompt_path = scratch_dir / f"wrapper-{session_name}-prompt.txt"
    prompt_path.write_text(full_prompt, encoding="utf-8")

    # Step 5-12: Try/finally block for cleanup
    try:
        session_owned_by_us: bool = False
        session_reused: bool = False

        # Reuse short-circuit: check if named session already exists
        if args.psmux_session is not None:
            existing = _psmux.list_sessions()
            if args.psmux_session in existing:
                # Session exists; check if it's idle
                timeout = _resolve_reuse_idle_timeout_s()
                if not _wait_for_idle_prompt(session_name, timeout):
                    raise RuntimeError(
                        f"cannot reuse psmux session {session_name}: not idle within {int(timeout)}s"
                    )
                print(
                    f"[millpy-claude-sub] reusing psmux session {session_name}",
                    file=sys.stderr
                )
                session_reused = True
            else:
                # Session doesn't exist; create it
                try:
                    _psmux.new_session(
                        session_name, shell_argv=["pwsh", "-NoLogo", "-NoProfile"]
                    )
                    time.sleep(POLL_INTERVAL_S)
                    _psmux.set_history_limit(session_name, 50000)
                except _psmux.PsmuxError as exc:
                    raise RuntimeError(f"failed to create psmux session: {exc}") from exc
                session_owned_by_us = True

                # Step 7: Startup check for claude binary
                _psmux.send_keys(
                    session_name,
                    "Get-Command claude -ErrorAction Stop; Write-Host CLAUDE_READY",
                    enter=True
                )
                if not _wait_for_marker_in_pane(
                    session_name, "CLAUDE_READY", BOOT_READY_TIMEOUT_S
                ):
                    tail = _psmux.capture_pane(session_name)
                    raise RuntimeError(
                        f"claude not found in psmux pane PATH (expected at ~/.local/bin/claude.exe). Pane tail: {tail}"
                    )
        else:
            # Auto-generated session name; always create
            try:
                _psmux.new_session(session_name, shell_argv=["pwsh", "-NoLogo", "-NoProfile"])
                time.sleep(POLL_INTERVAL_S)
                _psmux.set_history_limit(session_name, 50000)
            except _psmux.PsmuxError as exc:
                raise RuntimeError(f"failed to create psmux session: {exc}") from exc
            session_owned_by_us = True

            # Step 7: Startup check for claude binary
            _psmux.send_keys(
                session_name,
                "Get-Command claude -ErrorAction Stop; Write-Host CLAUDE_READY",
                enter=True
            )
            if not _wait_for_marker_in_pane(session_name, "CLAUDE_READY", BOOT_READY_TIMEOUT_S):
                tail = _psmux.capture_pane(session_name)
                raise RuntimeError(
                    f"claude not found in psmux pane PATH (expected at ~/.local/bin/claude.exe). Pane tail: {tail}"
                )

        # Step 8: Build claude launch command
        if not session_reused:
            claude_cmd_parts = [
                "claude",
                "--model", args.model,
                *MODE_TOOL_FLAGS[args.mode],
                "--session-id", args.session_id,
            ]
            if args.effort:
                claude_cmd_parts += ["--effort", args.effort]
            claude_cmd_str = _ps_join(claude_cmd_parts)

            # Step 9: Launch claude and wait for idle prompt
            print(f"[millpy-claude-sub] launching: {claude_cmd_str!r}", file=sys.stderr)
            _psmux.send_keys(session_name, claude_cmd_str, enter=True)
            if not _wait_for_idle_prompt(session_name, BOOT_READY_TIMEOUT_S):
                tail = _psmux.capture_pane(session_name, alternate=True)
                tail_lines = [ln for ln in tail.splitlines() if ln.strip()]
                print(f"[millpy-claude-sub] boot-debug: {len(tail_lines)} nonempty lines in alt screen", file=sys.stderr)
                for ln in tail_lines[:20]:
                    print(f"[millpy-claude-sub] boot-debug line: {ln.encode('ascii','replace').decode()!r}", file=sys.stderr)
                raise RuntimeError("claude TUI did not reach idle prompt within boot timeout")

        # Step 10: Submit prompt via bracketed paste (preserves multi-line text).
        # paste-buffer converts \n to \r, but within \e[200~...\e[201~] the TUI
        # buffers all content without treating \r as Enter. Enter submits after.
        _psmux.load_buffer(session_name, "p", prompt_path)
        _psmux.send_keys(session_name, "\x1b[200~", literal=True)
        _psmux.paste_buffer(session_name, "p")
        _psmux.send_keys(session_name, "\x1b[201~", literal=True)
        time.sleep(POLL_INTERVAL_S)
        _psmux.send_keys(session_name, "Enter", enter=False)

        # Step 11: Poll for response using markers
        start = time.monotonic()
        while True:
            elapsed = time.monotonic() - start
            capture = _psmux.capture_pane(session_name, alternate=True)
            try:
                response = _psmux_capture.extract_response(capture, begin_marker, end_marker)
                print(response, end="")
                print(
                    json.dumps({
                        "session_id": args.session_id,
                        "duration_s": round(elapsed, 2),
                        "mode": args.mode
                    }),
                    file=sys.stderr
                )
                # Success-path cleanup: kill session only if not keeping alive
                if not args.keep_alive:
                    try:
                        _psmux.kill_session(session_name)
                    except _psmux.PsmuxError:
                        pass
                else:
                    print(
                        f"[millpy-claude-sub] keepalive: leaving psmux session {session_name} running",
                        file=sys.stderr
                    )
                return 0
            except _psmux_capture.MarkerNotFoundError:
                if elapsed > RESPONSE_POLL_TIMEOUT_S[args.mode]:
                    raise RuntimeError(
                        f"response-poll timeout: mode={args.mode} elapsed={elapsed:.1f}s"
                    )
                time.sleep(POLL_INTERVAL_S)

    except Exception as exc:
        print(f"[millpy-claude-sub] {type(exc).__name__}: {exc}", file=sys.stderr)
        # Error-path cleanup: kill session only if we owned it
        if session_owned_by_us:
            try:
                _psmux.kill_session(session_name)
                print(
                    f"[millpy-claude-sub] error cleanup: killed psmux session {session_name}",
                    file=sys.stderr
                )
            except _psmux.PsmuxError:
                pass
        return 1
    finally:
        prompt_path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
