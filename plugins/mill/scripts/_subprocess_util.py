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
import threading
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

    Windows watchdog:
        When ``timeout`` is not None on Windows, a watchdog loop enforces
        the deadline instead of relying on ``proc.communicate(timeout=)``.
        Background daemon threads drain ``proc.stdout`` / ``proc.stderr``
        via ``readline()`` into in-memory buffers; a third daemon thread
        writes ``input`` to ``proc.stdin`` when supplied. The main thread
        polls ``proc.poll()`` every 100 ms. On normal exit the threads are
        joined and output assembled from the buffers. On deadline breach
        ``taskkill /T /F /PID`` kills the full process tree (including
        grandchildren), threads are joined with a 1 s grace, and
        ``subprocess.TimeoutExpired`` is raised with whatever was collected.
        POSIX uses the existing ``communicate(timeout=)`` + ``os.killpg``
        path unchanged.
    """
    child_env = env.copy() if env is not None else os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"

    _spawn_msg = f"[subprocess] spawn argv={argv!r} timeout={timeout}"
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
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        popen_kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen(argv, **popen_kwargs)
    except Exception as exc:
        print(_spawn_msg, file=sys.stderr)
        print(f"[subprocess] Popen raised: {exc!r}", file=sys.stderr)
        raise

    if os.name == "nt" and timeout is not None:
        try:
            stdout_out, stderr_out = _run_windows_watchdog(
                proc, argv=argv, input=input, timeout=timeout, start=start
            )
        except subprocess.TimeoutExpired:
            print(_spawn_msg, file=sys.stderr)
            raise
    else:
        try:
            stdout_out, stderr_out = proc.communicate(input=input, timeout=timeout)
            stdout_out = stdout_out or ""
            stderr_out = stderr_out or ""
        except subprocess.TimeoutExpired as exc:
            print(_spawn_msg, file=sys.stderr)
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

    if proc.returncode != 0:
        print(_spawn_msg, file=sys.stderr)
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


def _run_windows_watchdog(
    proc: subprocess.Popen,
    *,
    argv: list[str],
    input: str | None,
    timeout: float,
    start: float,
) -> tuple[str, str]:
    """
    Enforce ``timeout`` on Windows by polling ``proc.poll()`` and killing
    the full tree with ``taskkill /T /F`` when the deadline trips.

    Returns ``(stdout_out, stderr_out)`` strings on normal completion.
    Raises ``subprocess.TimeoutExpired`` on deadline breach.
    """
    endtime = time.monotonic() + timeout
    stdout_buf: list[str] = []
    stderr_buf: list[str] = []
    stdout_lock = threading.Lock()
    stderr_lock = threading.Lock()
    reader_threads: list[threading.Thread] = []

    if proc.stdout is not None:
        def _drain_stdout() -> None:
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                with stdout_lock:
                    stdout_buf.append(line)

        t = threading.Thread(target=_drain_stdout, daemon=True)
        t.start()
        reader_threads.append(t)

    if proc.stderr is not None:
        def _drain_stderr() -> None:
            while True:
                line = proc.stderr.readline()
                if not line:
                    break
                with stderr_lock:
                    stderr_buf.append(line)

        t = threading.Thread(target=_drain_stderr, daemon=True)
        t.start()
        reader_threads.append(t)

    if input is not None:
        def _write_stdin() -> None:
            proc.stdin.write(input)
            proc.stdin.close()

        threading.Thread(target=_write_stdin, daemon=True).start()

    while proc.poll() is None and time.monotonic() < endtime:
        time.sleep(0.1)

    if proc.poll() is not None:
        for t in reader_threads:
            t.join(timeout=1.0)
        return "".join(stdout_buf), "".join(stderr_buf)

    # Deadline tripped — kill the full process tree.
    print(
        f"[subprocess] exit code=timeout duration={time.monotonic() - start:.3f}s",
        file=sys.stderr,
    )
    subprocess.run(
        ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
        capture_output=True,
    )
    try:
        proc.wait(timeout=_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        pass
    for t in reader_threads:
        t.join(timeout=1.0)
    collected_stdout = "".join(stdout_buf)
    collected_stderr = "".join(stderr_buf)
    raise subprocess.TimeoutExpired(
        cmd=argv,
        timeout=timeout,
        output=collected_stdout,
        stderr=collected_stderr,
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
    """Fire-and-forget detached subprocess. Returns the Popen handle.

    Windows: pid shift.
        On Windows the returned ``Popen.pid`` is the intermediate ``cmd.exe``
        shim PID, which exits immediately after dispatching ``start /B``.
        The authoritative worker PID is recorded by the worker itself in the
        ``[mill-bg] WORKER PID=<pid> START <iso8601>`` log sentinel (written
        in batch 2). No current caller of ``popen_detached`` consumes the
        returned pid for process management — all callers poll the log file
        for the EXIT sentinel instead.

        The two-stage ``cmd /c start "" /B /MIN`` launch escapes the parent's
        Win32 Job Object so the worker survives launcher exit under VS Code /
        CC Bash (fix for #271). ``CREATE_BREAKAWAY_FROM_JOB`` is retained as
        a belt-and-braces fallback for environments where the intermediate
        ``cmd`` is itself in a non-breakaway job.
    """
    child_env = (env or os.environ).copy()
    child_env["PYTHONIOENCODING"] = "utf-8"

    print(f"[subprocess] popen_detached argv={argv!r}", file=sys.stderr)

    popen_kwargs: dict = dict(stdin=stdin, stdout=stdout, stderr=stderr, cwd=cwd, env=child_env)
    if os.name == "nt":
        # Two-stage launch: cmd.exe shim dispatches via `start /B`, escaping
        # the parent's Win32 Job Object. The empty "" is the required title
        # argument for `start` — omitting it causes the first real argument
        # to be misinterpreted when the path contains spaces.
        # DETACHED_PROCESS is intentionally omitted — see comment above on
        # CREATE_NO_WINDOW being sufficient and DETACHED_PROCESS causing a
        # console flash when combined with CREATE_NO_WINDOW.
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | _CREATE_BREAKAWAY_FROM_JOB
        )
        launch_argv = ["cmd", "/c", "start", "", "/B", "/MIN"] + argv
    else:
        popen_kwargs["start_new_session"] = True
        launch_argv = argv

    return subprocess.Popen(launch_argv, **popen_kwargs)
