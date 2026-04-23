"""
Single subprocess.run wrapper used by every mill script.

Centralising subprocess invocation here gives us three things that were
painful to maintain case-by-case in v1:

1. UTF-8 is enforced everywhere. The child environment gets
   PYTHONIOENCODING=utf-8 injected, and stdout/stderr are decoded with
   encoding="utf-8", errors="replace". This eliminates the class of bugs
   where a Windows console's cp1252 default mangled git or claude-cli
   output.
2. Every spawn and exit is echoed to stderr as a one-line breadcrumb
   (``[subprocess] spawn argv=... timeout=...`` / ``exit code=... duration=...s``).
   Smoke tests can grep this stream to assert what was (or wasn't) spawned.
3. Timeouts propagate as ``subprocess.TimeoutExpired`` after emitting a
   matching exit breadcrumb, so callers don't have to log their own.

Public API:
    run(argv, *, cwd=None, input=None, check=False, timeout=None, env=None)
        Thin wrapper around ``subprocess.run`` with the guarantees above.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def run(
    argv: list[str],
    *,
    cwd: Path | str | None = None,
    input: str | None = None,
    check: bool = False,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """
    Run a subprocess with UTF-8 text I/O and spawn/exit breadcrumbs on stderr.

    The child environment is a shallow copy of either the caller-supplied
    ``env`` or ``os.environ``, with ``PYTHONIOENCODING=utf-8`` always
    injected so child Python processes don't fall back to cp1252 on
    Windows. Stdout and stderr are captured as decoded text
    (``encoding="utf-8"``, ``errors="replace"``).

    Args:
        argv: Command and arguments to execute.
        cwd: Working directory for the child. ``None`` inherits the
            caller's cwd.
        input: Optional string fed to the child's stdin.
        check: When True, ``subprocess.run`` raises CalledProcessError on
            non-zero exit. Default False — callers inspect
            ``result.returncode`` explicitly.
        timeout: Seconds before the child is killed and
            ``subprocess.TimeoutExpired`` is raised. A matching exit
            breadcrumb is emitted before the exception propagates.
        env: Full replacement environment. When None, inherits from
            ``os.environ``.

    Returns:
        The completed ``subprocess.CompletedProcess[str]`` — stdout,
        stderr, and returncode populated as strings.
    """
    # Build the child environment. Start from the caller's env (or the
    # current process env), then force UTF-8 I/O so nested Python children
    # don't default to cp1252 on Windows.
    child_env = env.copy() if env is not None else os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"

    # Emit a spawn breadcrumb. Tests and post-mortem debugging rely on this
    # line being present on stderr before the child starts executing.
    print(f"[subprocess] spawn argv={argv!r} timeout={timeout}", file=sys.stderr)
    start = time.monotonic()
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            input=input,
            check=check,
            timeout=timeout,
            env=child_env,
            encoding="utf-8",
            errors="replace",
            text=True,
            capture_output=True,
        )
    except subprocess.TimeoutExpired:
        # Still emit an exit breadcrumb on timeout so the stderr stream
        # always has a matching spawn/exit pair per invocation.
        print(
            f"[subprocess] exit code=timeout duration={time.monotonic() - start:.3f}s",
            file=sys.stderr,
        )
        raise
    # Normal completion — log exit code and wall duration.
    print(
        f"[subprocess] exit code={result.returncode} duration={time.monotonic() - start:.3f}s",
        file=sys.stderr,
    )
    return result
