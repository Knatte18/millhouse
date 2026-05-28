"""Liveness probe for millpy-bg worker subprocesses; used by orchestrators after resume to decide whether to wait or re-fire."""
import logging
import os
import re
import time
from pathlib import Path

_logger = logging.getLogger(__name__)

_PID_RE = re.compile(r"\[mill-bg\] WORKER PID=(\d+) START")
_EXIT_RE = re.compile(r"\[mill-bg\] EXIT \d+")
_STALE_LOG_SECONDS = 5 * 60


def is_bg_worker_alive(log_path: Path) -> tuple[bool, int | None]:
    """Check if a millpy-bg worker process is alive based on its log file.

    Reads the worker log header for [mill-bg] WORKER PID=N START, checks
    for [mill-bg] EXIT sentinel, and probes the PID's liveness via
    os.kill(pid, 0) with fallback to log mtime staleness on Windows EINVAL.

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
    if not log_path.exists():
        return (False, None)
    text = log_path.read_text(encoding="utf-8", errors="replace")
    m = _PID_RE.search(text)
    if not m:
        return (False, None)
    pid = int(m.group(1))
    if _EXIT_RE.search(text):
        return (False, pid)
    try:
        os.kill(pid, 0)
        return (True, pid)
    except ProcessLookupError:
        return (False, pid)
    except PermissionError:
        return (True, pid)
    except OSError as exc:
        # Unknown errno from os.kill (Windows-specific or transient) -- fall through to mtime fallback.
        _logger.debug("is_bg_worker_alive: os.kill(%s, 0) raised %r -- falling back to log-mtime staleness", pid, exc)
        pass
    mtime = log_path.stat().st_mtime
    if (time.time() - mtime) > _STALE_LOG_SECONDS:
        return (False, pid)
    return (True, pid)
