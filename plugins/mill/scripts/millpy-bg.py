"""
millpy-bg.py — project-local process backgrounder.

Launcher mode (default):
    millpy-bg.py --slug <slug> -- <cmd> [args...]

    Resolves the git root of the current directory, creates
    .scratch/bg-<YYYYMMDD-HHMMSS>-<slug>.log, spawns a detached
    worker process that runs <cmd> with stdout/stderr written to
    that log file, and prints:
        pid=<N> log=<path>

    (On Windows the pid is the cmd-shim launcher PID, which exits
    almost immediately after dispatching the worker; the authoritative
    worker PID is logged inside the file as [mill-bg] WORKER PID=...)

Worker mode (internal — spawned by launcher):
    millpy-bg.py --_worker --log <abs-path> -- <cmd> [args...]

    Runs <cmd> with stdout+stderr redirected to <abs-path> and
    appends "[mill-bg] EXIT <code>" when the process exits.
    Not intended to be called directly.
"""
import sys

# ── worker fast-path — stdlib only, no mill imports ──────────────────────────
if "--_worker" in sys.argv:
    import os
    import subprocess
    from datetime import datetime, timezone

    def _worker_main(args: list[str]) -> int:
        try:
            sep = args.index("--")
        except ValueError:
            print("mill-bg worker: missing '--' separator", file=sys.stderr)
            return 1
        flags = args[:sep]
        cmd = args[sep + 1:]
        if not cmd:
            print("mill-bg worker: empty command after '--'", file=sys.stderr)
            return 1
        log_path = None
        i = 0
        while i < len(flags):
            if flags[i] == "--log" and i + 1 < len(flags):
                log_path = flags[i + 1]
                i += 2
            else:
                i += 1
        if log_path is None:
            print("mill-bg worker: missing --log", file=sys.stderr)
            return 1
        exit_written = False
        try:
            with open(log_path, "w", encoding="utf-8", buffering=1) as log_f:
                log_f.write(
                    f"[mill-bg] WORKER PID={os.getpid()} START "
                    f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
                )
                result = subprocess.run(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                log_f.write(f"\n[mill-bg] EXIT {result.returncode}\n")
                log_f.flush()
                exit_written = True
            return 0
        except Exception as exc:
            try:
                with open(log_path, "a", encoding="utf-8") as log_f:
                    log_f.write(f"[mill-bg] WORKER ERROR {exc!r}\n")
                    log_f.flush()
            except Exception:
                print(f"[mill-bg] WORKER ERROR {exc!r}", file=sys.stderr)
            if not exit_written:
                try:
                    with open(log_path, "a", encoding="utf-8") as _lf:
                        _lf.write("[mill-bg] EXIT -1\n")
                        _lf.flush()
                except Exception:
                    pass
            return 1

    def main(argv: list[str] | None = None) -> int:
        args = argv if argv is not None else sys.argv[1:]
        worker_args = [a for a in args if a != "--_worker"]
        return _worker_main(worker_args)

    if __name__ == "__main__":
        sys.exit(main())
    sys.exit(0)

# ── launcher path ─────────────────────────────────────────────────────────────
import subprocess
import _subprocess_util
from datetime import datetime, timezone
from pathlib import Path


def _launcher_main(args: list[str]) -> int:
    try:
        sep = args.index("--")
    except ValueError:
        print("mill-bg: missing '--' separator", file=sys.stderr)
        return 1
    mill_args = args[:sep]
    cmd = args[sep + 1:]
    if not cmd:
        print("mill-bg: empty command after '--'", file=sys.stderr)
        return 1

    slug = None
    i = 0
    while i < len(mill_args):
        if mill_args[i] == "--slug" and i + 1 < len(mill_args):
            slug = mill_args[i + 1]
            i += 2
        else:
            i += 1
    if slug is None:
        print("mill-bg: missing --slug", file=sys.stderr)
        return 1

    git_result = _subprocess_util.run(["git", "rev-parse", "--show-toplevel"])
    if git_result.returncode != 0:
        print(
            f"mill-bg: git rev-parse failed: {git_result.stderr.strip()}",
            file=sys.stderr,
        )
        return 1
    git_root = git_result.stdout.strip()

    try:
        import _paths
        import _config
        import _marker

        wiki_path = _paths.resolve_wiki_path(Path(git_root))
        cfg = _config.load_config(Path(git_root), Path(git_root))
        _marker.slug_from_branch(Path(git_root), wiki_path, cfg)
    except _marker.MarkerError as exc:
        git_branch_result = _subprocess_util.run(
            ["git", "-C", git_root, "branch", "--show-current"]
        )
        branch = git_branch_result.stdout.strip() or "<detached>"
        print(
            f"mill-bg: cwd appears to be a non-task worktree "
            f"(branch={branch!r}, error: {exc}). Switch to the task-worktree "
            f"terminal before launching reviews.",
            file=sys.stderr,
        )
        return 1
    except (ValueError, SystemExit, OSError) as exc:
        print(
            f"mill-bg: cannot validate cwd ({exc}). Verify cwd is a task "
            f"worktree and config is loadable.",
            file=sys.stderr,
        )
        return 1

    scratch_dir = Path(git_root) / ".scratch"
    scratch_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    log_path = scratch_dir / f"bg-{timestamp}-{slug}.log"

    worker_argv = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--_worker",
        "--log",
        str(log_path),
        "--",
    ] + cmd

    proc = _subprocess_util.popen_detached(
        worker_argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # NOTE: on Windows (after the two-stage cmd /c start /B launch) proc.pid is
    # the cmd-shim PID, which exits almost immediately. The authoritative worker
    # PID is inside the log file as [mill-bg] WORKER PID=... sentinel.
    print(f"pid={proc.pid} log={log_path}")
    return 0


def _worker_main(args: list[str]) -> int:
    raise RuntimeError("_worker_main is only available in worker mode")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    return _launcher_main(args)


if __name__ == "__main__":
    sys.exit(main())
