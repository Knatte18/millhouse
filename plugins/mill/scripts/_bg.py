"""Liveness probe for millpy-bg worker subprocesses; used by orchestrators after resume to decide whether to wait or re-fire.

Completion detection (agent-mode dispatch preferred):
  - Agent-mode dispatch (no subprocess) is the structural solution — no process
    to lose and no detection needed.
  - Subprocess mode (millpy-bg dispatch) relies on two mechanisms:
    * EXIT sentinel write (best-effort, killed by hard termination).
    * Trailing-JSON completion sentinel (kill-resilient backstop).

check_bg_status determines completion via this resolution order:
  (1) log missing -> dead
  (2) [mill-bg] EXIT <code> present -> exit
  (3) liveness probe (affirmative kill-signal response) -> running
  (4) trailing-JSON completion sentinel present -> exit
  (5) liveness probe (assumed-alive mtime-fresh fallback) -> running
  (6) otherwise -> dead

Trailing-JSON contract: every millpy-bg-dispatched CLI MUST emit a single
parseable JSON line as its final stdout (used by step 4 above).
"""
import json
import logging
import os
import re
import time
from pathlib import Path

_logger = logging.getLogger(__name__)

_PID_RE = re.compile(r"\[mill-bg\] WORKER PID=(\d+) START")
_EXIT_RE = re.compile(r"\[mill-bg\] EXIT \d+")
_EXIT_CODE_RE = re.compile(r"\[mill-bg\] EXIT (\d+)")
_STALE_LOG_SECONDS = 5 * 60


def _has_valid_json_result(text: str) -> bool:
    """Check if text contains a valid JSON result as the last {-prefixed line.

    Scans text in reverse for the first line where line.strip().startswith("{"),
    attempts json.loads on that line, and returns True on success.
    Returns False if no such line is found or if parsing raises json.JSONDecodeError.
    Never raises.
    """
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped.startswith("{"):
            try:
                json.loads(stripped)
                return True
            except json.JSONDecodeError:
                return False
    return False


def _probe_liveness(log_path: Path) -> tuple[str, int | None]:
    """Probe worker liveness without collapsing affirmative vs assumed alive.

    Reads the worker log for [mill-bg] WORKER PID=N and [mill-bg] EXIT sentinel.
    Probes the PID via os.kill(pid, 0) with fallback to log mtime staleness.

    Returns (state, pid_or_None) where state is one of:
      - "exit"               -> [mill-bg] EXIT sentinel present
      - "affirmative-alive"  -> os.kill(pid, 0) succeeded or raised PermissionError
      - "assumed-alive"      -> os.kill raised inconclusive OSError/SystemError,
                               mtime is fresh (<=_STALE_LOG_SECONDS)
      - "dead"               -> no PID line, mtime stale, or no log file
    """
    if not log_path.exists():
        return ("dead", None)
    text = log_path.read_text(encoding="utf-8", errors="replace")
    m = _PID_RE.search(text)
    if not m:
        return ("dead", None)
    pid = int(m.group(1))
    if _EXIT_RE.search(text):
        return ("exit", pid)
    try:
        os.kill(pid, 0)
        return ("affirmative-alive", pid)
    except ProcessLookupError:
        return ("dead", pid)
    except PermissionError:
        return ("affirmative-alive", pid)
    except (OSError, SystemError) as exc:
        # Unknown errno from os.kill (Windows-specific or transient) -- fall through to mtime fallback.
        _logger.debug("_probe_liveness: os.kill(%s, 0) raised %r -- falling back to log-mtime staleness", pid, exc)
        pass
    mtime = log_path.stat().st_mtime
    if (time.time() - mtime) > _STALE_LOG_SECONDS:
        return ("dead", pid)
    return ("assumed-alive", pid)


def is_bg_worker_alive(log_path: Path) -> tuple[bool, int | None]:
    """Check if a millpy-bg worker process is alive based on its log file.

    Thin wrapper over _probe_liveness that collapses the four liveness states
    into a boolean (True for affirmative-alive or assumed-alive; False for exit or dead).

    Returns (alive, pid_or_None):
      - log file does not exist                   -> (False, None)
      - log has no WORKER PID line                -> (False, None)
      - log has WORKER PID AND [mill-bg] EXIT     -> (False, pid)
      - kill probe succeeds (process alive)       -> (True, pid)
      - kill(ESRCH) or kill(EPERM)                -> handled; EPERM is alive
      - kill raises unknown OSError, fallback:
        - log mtime > 5 min old                   -> (False, pid)
        - log mtime <= 5 min old                  -> (True, pid)
    """
    state, pid = _probe_liveness(log_path)
    if state in ("affirmative-alive", "assumed-alive"):
        return (True, pid)
    return (False, pid)


def check_bg_status(log_path: Path) -> tuple[str, int | None]:
    """Single-shot, non-blocking worker status check.

    Returns immediately with the worker's current status and metadata.
    Performs exactly one status determination without looping or sleeping.
    The orchestrator owns the poll cadence.

    Resolution order (first match wins):
      (1) log file does not exist                     -> ("dead", None)
      (2) log contains [mill-bg] EXIT <code>          -> ("exit", code)
      (3) probe is "affirmative-alive" (kill succeeded) -> ("running", pid)
      (4) valid trailing JSON completion sentinel     -> ("exit", 0)
      (5) probe is "assumed-alive" (mtime-fresh)     -> ("running", pid)
      (6) otherwise                                   -> ("dead", pid)

    This ordering ensures a worker that finished (emitted trailing JSON) but was
    hard-killed before writing EXIT is recognized as completed on the next poll,
    while still respecting an affirmatively-alive process even if it has JSON-looking
    output mid-stream.
    """
    if not log_path.exists():
        return ("dead", None)
    text = log_path.read_text(encoding="utf-8", errors="replace")
    m = _EXIT_CODE_RE.search(text)
    if m:
        code = int(m.group(1))
        return ("exit", code)
    state, pid = _probe_liveness(log_path)
    if state == "affirmative-alive":
        return ("running", pid)
    if _has_valid_json_result(text):
        return ("exit", 0)
    if state == "assumed-alive":
        return ("running", pid)
    return ("dead", pid)
