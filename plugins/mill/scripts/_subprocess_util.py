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
    run(argv, *, cwd=None, input=None, check=False, timeout=None, env=None,
        stdout=None, stderr=None)
        Thin wrapper around ``subprocess.Popen`` with the guarantees above.
    popen_detached(argv, *, stdin=None, stdout=None, stderr=None, cwd=None, env=None)
        Fire-and-forget detached subprocess. Returns the Popen handle.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

_GRACE_SECONDS = 5
# CREATE_BREAKAWAY_FROM_JOB is not exported by the subprocess module.
_CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def run(
    argv: list[str],
    *,
    cwd: Path | str | None = None,
    input: str | None = None,
    check: bool = False,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
    stdout=None,
    stderr=None,
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
        check: When True, raises CalledProcessError on non-zero exit.
            Default False — callers inspect ``result.returncode`` explicitly.
        timeout: Seconds before the child process tree is killed and
            ``subprocess.TimeoutExpired`` is raised. A matching exit
            breadcrumb is emitted before the exception propagates.
        env: Full replacement environment. When None, inherits from
            ``os.environ``.
        stdout: Override for the stdout stream. When None (default),
            ``subprocess.PIPE`` is used and output is captured. When
            overridden, the caller's value flows directly to
            ``subprocess.Popen``.
        stderr: Override for the stderr stream. Same semantics as
            ``stdout``.

    Returns:
        The completed ``subprocess.CompletedProcess[str]`` — stdout,
        stderr, and returncode populated as strings.

    Note:
        When stdout/stderr are overridden to non-PIPE values, the returned
        CompletedProcess.stdout/.stderr are empty strings — capture is
        impossible without PIPE.
    """
    child_env = env.copy() if env is not None else os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"

    print(f"[subprocess] spawn argv={argv!r} timeout={timeout}", file=sys.stderr)
    start = time.monotonic()

    popen_kwargs: dict = dict(
        stdout=subprocess.PIPE if stdout is None else stdout,
        stderr=subprocess.PIPE if stderr is None else stderr,
        cwd=cwd,
        env=child_env,
        encoding="utf-8",
        errors="replace",
        text=True,
    )
    if input is not None:
        popen_kwargs["stdin"] = subprocess.PIPE
    if os.name == "nt":
        # Suppress the CMD console window that would otherwise flash on-screen
        # when spawning `cmd /c claude` or `git` on Windows.
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(argv, **popen_kwargs)
    try:
        stdout_out, stderr_out = proc.communicate(input=input, timeout=timeout)
        stdout_out = stdout_out or ""
        stderr_out = stderr_out or ""
    except subprocess.TimeoutExpired as exc:
        print(
            f"[subprocess] exit code=timeout duration={time.monotonic() - start:.3f}s",
            file=sys.stderr,
        )
        collected_stdout = exc.stdout
        collected_stderr = exc.stderr
        proc.terminate()
        try:
            proc.wait(timeout=_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                    capture_output=True,
                )
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait()
        raise subprocess.TimeoutExpired(
            cmd=argv,
            timeout=timeout,
            output=collected_stdout,
            stderr=collected_stderr,
        ) from exc

    print(
        f"[subprocess] exit code={proc.returncode} duration={time.monotonic() - start:.3f}s",
        file=sys.stderr,
    )
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode, argv, output=stdout_out, stderr=stderr_out
        )
    return subprocess.CompletedProcess(
        args=argv, returncode=proc.returncode, stdout=stdout_out, stderr=stderr_out
    )


def popen_detached(
    argv: list[str],
    *,
    stdin=None,
    stdout=None,
    stderr=None,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.Popen:
    """Fire-and-forget detached subprocess. Returns the Popen handle."""
    child_env = (env or os.environ).copy()
    child_env["PYTHONIOENCODING"] = "utf-8"

    print(f"[subprocess] popen_detached argv={argv!r}", file=sys.stderr)

    popen_kwargs: dict = dict(stdin=stdin, stdout=stdout, stderr=stderr, cwd=cwd, env=child_env)
    if os.name == "nt":
        # DETACHED_PROCESS combined with CREATE_NO_WINDOW is known to cause
        # a brief console window to flash on screen — DETACHED_PROCESS can
        # trigger console-creation that overrides CREATE_NO_WINDOW for the
        # child process group. Use CREATE_NO_WINDOW alone (plus the process-
        # group / breakaway flags needed for true detachment) and skip
        # DETACHED_PROCESS entirely. CREATE_NO_WINDOW ensures no console is
        # ever attached, which is what we actually want.
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | _CREATE_BREAKAWAY_FROM_JOB
        )
    else:
        popen_kwargs["start_new_session"] = True

    return subprocess.Popen(argv, **popen_kwargs)
