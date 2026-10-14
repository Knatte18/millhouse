"""
Shared runner for every verify command mill executes.

Public API:
    run_verify          run one command with a timeout, tree kill, live progress lines,
                        an output file and an optional ``## Verify log`` row in status.md.
    VerifyRun           the result record (``summary()`` gives the loggable subset).
    timeout_seconds     read ``pipeline.verify_timeout_minutes`` from a loaded config.
    resolve_status_path locate an existing status.md for the Verify log row.
    timeout_prefix / output_suffix
                        the failure-reason fragments callers wrap around command output.

The child's stdout and stderr go to a file, never a pipe, so a grandchild that inherits
the handle cannot keep the runner waiting after the command itself has exited.
All printed output is ASCII.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import _paths
import _status
import _timestamp

DEFAULT_TIMEOUT_MINUTES = 20
HEARTBEAT_INTERVAL_S = 30
CMD_FIELD_MAX = 300

_SHELL_MODES = {"posix", "native"}


@dataclass
class VerifyRun:
    """
    Outcome of one verify command.

    ``exit_code`` is ``None`` when the command timed out or could not be launched;
    ``timed_out`` distinguishes the two.
    ``output`` is the decoded combined stdout and stderr, also saved at ``output_path``.
    """

    label: str
    cmd: str
    cwd: Path
    exit_code: int | None
    wall_s: float
    first_run: bool
    timed_out: bool
    output: str
    output_path: Path | None
    timeout_s: float

    def summary(self) -> dict:
        """Return the loggable subset: label, cmd, exit_code, wall_s, first_run, timed_out."""
        return {
            "label": self.label,
            "cmd": self.cmd,
            "exit_code": self.exit_code,
            "wall_s": round(self.wall_s, 1),
            "first_run": self.first_run,
            "timed_out": self.timed_out,
        }


def _posix_shell_run_args(cmd: str) -> tuple:
    """
    Build subprocess.run args to route POSIX shell commands through bash on Windows.

    On Windows (os.name == "nt"), when bash is available, returns args to invoke bash -c explicitly.
    On other platforms or when bash is unavailable, returns the command string with shell=True so
    the native shell processes it.

    POSIX verify commands often start with "PYTHONPATH= " (env-prefix syntax) that cmd.exe cannot
    parse.
    Running through bash honours this syntax cross-platform.

    Args:
        cmd: The command string (e.g., "PYTHONPATH= pytest tests/ -q").

    Returns:
        A tuple (run_args, run_kwargs) where run_args is either a list ([bash, "-c", cmd]) or a
        string (cmd), and run_kwargs is either {} or {"shell": True} to be unpacked into
        subprocess.run.
    """
    bash = shutil.which("bash") if os.name == "nt" else None
    if bash:
        return [bash, "-c", cmd], {}
    return cmd, {"shell": True}


def timeout_seconds(cfg: dict) -> float:
    """
    Return the per-command verify timeout in seconds from ``pipeline.verify_timeout_minutes``.

    An absent key yields the default of ``DEFAULT_TIMEOUT_MINUTES``.

    Raises:
        ValueError: the key is present but not a positive int or float.
    """
    pipeline = cfg.get("pipeline") or {}
    if "verify_timeout_minutes" not in pipeline:
        return DEFAULT_TIMEOUT_MINUTES * 60
    minutes = pipeline["verify_timeout_minutes"]
    if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or minutes <= 0:
        raise ValueError(
            f"pipeline.verify_timeout_minutes must be a positive number, got {minutes!r}"
        )
    return minutes * 60


def resolve_status_path(hub_root: Path, cfg: dict) -> Path | None:
    """Return the hub's status.md path when the file exists, else ``None``."""
    try:
        path = _paths.status_path(hub_root, cfg)
    except KeyError:
        return None
    return path if path.exists() else None


def timeout_prefix(run: VerifyRun) -> str:
    """Return the failure-reason prefix naming the timeout and the verify label."""
    return f"[verify timed out after {int(run.timeout_s)}s: {run.label}] "


def output_suffix(run: VerifyRun) -> str:
    """Return the failure-reason suffix pointing at the saved output file, or ``""``."""
    if run.output_path is None:
        return ""
    return f"\n[verify output: {run.output_path}]"


def _emit_marker(verify_dir: Path, text: str) -> None:
    """Print one timestamped marker line to stderr and append it to ``verify.log``."""
    line = f"[verify] {_timestamp.now_utc_iso()} {text}"
    print(line, file=sys.stderr, flush=True)
    # The live log is a convenience; failing to write it must never change the verdict.
    try:
        with open(verify_dir / "verify.log", "a", encoding="utf-8") as log_file:
            log_file.write(line + "\n")
            log_file.flush()
    except Exception:
        pass


def _unique_output_path(verify_dir: Path, label: str) -> Path:
    """Return a not-yet-existing ``<timestamp>-<label>[-N].out`` path inside ``verify_dir``."""
    stem = f"{_timestamp.now_utc_compact()}-{_paths.sanitize_filename_component(label)}"
    candidate = verify_dir / f"{stem}.out"
    counter = 2
    while candidate.exists():
        candidate = verify_dir / f"{stem}-{counter}.out"
        counter += 1
    return candidate


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """Kill ``proc`` and every descendant immediately, with no terminate step."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_verify(
    cmd: str,
    *,
    cwd: Path,
    label: str,
    git_root: Path,
    timeout_s: float,
    shell_mode: str,
    env: dict | None = None,
    status_path: Path | None = None,
) -> VerifyRun:
    """
    Run one verify command with a timeout and full instrumentation.

    The command's combined output goes to ``<git_root>/.scratch/verify/<timestamp>-<label>.out``.
    START, HEARTBEAT and END lines go to stderr and ``.scratch/verify/verify.log``.
    When ``status_path`` is given, one ``## Verify log`` row is appended to it.
    A timeout kills the command's whole process tree.

    Args:
        cmd: The command string.
        cwd: Directory the command runs in.
        label: Short name of the verify site, used in file names, markers and the log row.
        git_root: Checkout whose ``.scratch/verify/`` directory holds the output and markers.
        timeout_s: Seconds before the command is killed.
        shell_mode: ``"posix"`` routes through bash where available; ``"native"`` uses the
            platform shell.
        env: Child environment; defaults to the current environment.
        status_path: status.md to receive the Verify log row, or ``None`` to skip it.

    Returns:
        A ``VerifyRun``.
        Command failure, timeout and launch failure are reported in the record, never raised.

    Raises:
        ValueError: ``cwd`` is ``None`` or ``shell_mode`` is not ``"posix"`` or ``"native"``.
    """
    if cwd is None:
        raise ValueError("run_verify requires a cwd")
    if shell_mode not in _SHELL_MODES:
        raise ValueError(f"shell_mode must be one of {sorted(_SHELL_MODES)}, got {shell_mode!r}")

    verify_dir = git_root / ".scratch" / "verify"
    verify_dir.mkdir(parents=True, exist_ok=True)
    first_run_marker = verify_dir / "first-run.done"
    first_run = not first_run_marker.exists()
    output_path = _unique_output_path(verify_dir, label)

    child_env = dict(env if env is not None else os.environ)
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["MSBUILDDISABLENODEREUSE"] = "1"
    child_env["DOTNET_CLI_USE_MSBUILD_SERVER"] = "0"

    popen_kwargs: dict = {
        "cwd": cwd,
        "env": child_env,
        "stdin": subprocess.DEVNULL,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        )
    else:
        popen_kwargs["start_new_session"] = True

    if shell_mode == "posix":
        run_args, shell_kwargs = _posix_shell_run_args(cmd)
    else:
        run_args, shell_kwargs = cmd, {"shell": True}

    cmd_field = _status.normalize_log_field(cmd, CMD_FIELD_MAX)
    label_field = _status.normalize_log_field(label)
    cwd_field = _status.normalize_log_field(str(cwd))

    _emit_marker(
        verify_dir,
        f"START {label_field} first_run={'true' if first_run else 'false'} "
        f"timeout={int(timeout_s)}s cwd={cwd_field} cmd={cmd_field}",
    )

    started = time.monotonic()
    heartbeat_stop = threading.Event()

    def heartbeat() -> None:
        while not heartbeat_stop.wait(HEARTBEAT_INTERVAL_S):
            _emit_marker(
                verify_dir,
                f"HEARTBEAT {label_field} elapsed={int(time.monotonic() - started)}s cmd={cmd_field}",
            )

    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()

    exit_code: int | None = None
    timed_out = False
    launch_error: str | None = None
    try:
        try:
            with open(output_path, "wb") as output_file:
                started = time.monotonic()
                proc = subprocess.Popen(
                    run_args, **shell_kwargs, stdout=output_file, **popen_kwargs
                )
                try:
                    exit_code = proc.wait(timeout=timeout_s)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    _kill_process_tree(proc)
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        pass
        except OSError as exc:
            launch_error = str(exc)
        wall_s = time.monotonic() - started
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join()

    if launch_error is not None:
        output = launch_error
        outcome: int | str = "launch-error"
    else:
        output = output_path.read_bytes().decode("utf-8", errors="replace")
        outcome = "timeout" if timed_out else exit_code

    _emit_marker(
        verify_dir, f"END {label_field} exit={outcome} wall={wall_s:.1f}s output={output_path}"
    )
    first_run_marker.touch()

    if status_path is not None:
        try:
            _status.append_verify_log(
                status_path,
                timestamp=_timestamp.now_utc_iso(),
                label=label,
                exit=outcome,
                wall_s=wall_s,
                first_run=first_run,
                cmd=cmd,
            )
        except Exception as exc:
            print(f"[verify] could not write Verify log row: {exc}", file=sys.stderr, flush=True)
    else:
        print(
            f"[verify] no status.md -- Verify log row skipped for {label_field}",
            file=sys.stderr,
            flush=True,
        )

    return VerifyRun(
        label=label,
        cmd=cmd,
        cwd=cwd,
        exit_code=exit_code,
        wall_s=wall_s,
        first_run=first_run,
        timed_out=timed_out,
        output=output,
        output_path=output_path,
        timeout_s=timeout_s,
    )
