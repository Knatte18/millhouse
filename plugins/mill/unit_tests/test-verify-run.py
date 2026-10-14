"""Unit tests for plugins/mill/scripts/_verify_run.py.

Children are short-lived ``sys.executable`` scripts written to a temp dir, so the
tests do not depend on shell-quoting differences across platforms.
"""
from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import time
import unittest.mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _status  # noqa: E402
import _verify_run  # noqa: E402

errors = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    """Print PASS/FAIL for one case and count failures."""
    global errors
    if condition:
        print(f"PASS: {name}")
    else:
        print(f"FAIL: {name} {detail}", file=sys.stderr)
        errors += 1


def write_script(directory: Path, name: str, body: str) -> str:
    """Write a python script and return a shell command string that runs it."""
    path = directory / name
    path.write_text(body, encoding="utf-8")
    return f'"{Path(sys.executable).as_posix()}" "{path.as_posix()}"'


def run(cmd: str, git_root: Path, **overrides):
    """Run ``cmd`` through run_verify with test defaults, capturing stderr."""
    kwargs = dict(
        cwd=git_root,
        label="t-label",
        git_root=git_root,
        timeout_s=30,
        shell_mode="posix",
    )
    kwargs.update(overrides)
    captured = io.StringIO()
    with contextlib.redirect_stderr(captured):
        result = _verify_run.run_verify(cmd, **kwargs)
    return result, captured.getvalue()


def pid_alive(pid: int) -> bool:
    """Report whether a process with ``pid`` still exists."""
    if os.name == "nt":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True
        ).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def wait_gone(pid: int, seconds: float = 10.0) -> bool:
    """Poll until ``pid`` is gone; return False when it outlives ``seconds``."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not pid_alive(pid):
            return True
        time.sleep(0.2)
    return not pid_alive(pid)


def kill_pid(pid: int) -> None:
    """Best-effort kill used for test cleanup."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


GRANDCHILD_PARENT = """
import subprocess, sys
child = subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep({sleep})"],
    stdout=sys.stdout,
    stderr=sys.stderr,
)
open(r"{pidfile}", "w").write(str(child.pid))
{tail}
"""


def test_pipe_trap(tmp: Path) -> None:
    pidfile = tmp / "grandchild.pid"
    cmd = write_script(
        tmp,
        "trap.py",
        GRANDCHILD_PARENT.format(sleep=30, pidfile=pidfile, tail="sys.exit(0)"),
    )
    started = time.monotonic()
    result, _ = run(cmd, tmp)
    elapsed = time.monotonic() - started
    try:
        check(
            "pipe trap: returns promptly with exit 0 while a grandchild holds stdout",
            elapsed < 10 and result.exit_code == 0,
            f"elapsed={elapsed:.1f} exit={result.exit_code}",
        )
    finally:
        if pidfile.exists():
            kill_pid(int(pidfile.read_text()))


def test_timeout(tmp: Path) -> None:
    pidfile = tmp / "timeout-grandchild.pid"
    cmd = write_script(
        tmp,
        "hang.py",
        GRANDCHILD_PARENT.format(
            sleep=60, pidfile=pidfile, tail="import time; time.sleep(60)"
        ),
    )
    result, _ = run(cmd, tmp, timeout_s=3)
    check("timeout: timed_out set and exit_code None", result.timed_out and result.exit_code is None)
    pid = int(pidfile.read_text()) if pidfile.exists() else None
    check("timeout: grandchild pid was recorded", pid is not None)
    if pid is not None:
        gone = wait_gone(pid)
        if not gone:
            kill_pid(pid)
        check("timeout: grandchild killed with the tree", gone)


def test_first_run_marker(tmp: Path) -> None:
    root = tmp / "first-run"
    root.mkdir()
    fail_cmd = write_script(tmp, "fail.py", "import sys; sys.exit(3)")
    first, _ = run(fail_cmd, root)
    second, _ = run(fail_cmd, root)
    check(
        "first-run marker: True then False",
        first.first_run is True and second.first_run is False and first.exit_code == 3,
    )
    check("first-run marker exists after a failing run", (root / ".scratch" / "verify" / "first-run.done").exists())

    root2 = tmp / "first-run-timeout"
    root2.mkdir()
    hang_cmd = write_script(tmp, "hang2.py", "import time; time.sleep(60)")
    run(hang_cmd, root2, timeout_s=1)
    check(
        "first-run marker exists after a timeout",
        (root2 / ".scratch" / "verify" / "first-run.done").exists(),
    )


def test_markers(tmp: Path) -> None:
    root = tmp / "markers"
    root.mkdir()
    cmd = write_script(tmp, "sleepy.py", "import time; time.sleep(0.3)")
    with unittest.mock.patch.object(_verify_run, "HEARTBEAT_INTERVAL_S", 0.05):
        _, stderr_text = run(cmd, root)
    log_text = (root / ".scratch" / "verify" / "verify.log").read_text(encoding="utf-8")
    for source_name, text in (("stderr", stderr_text), ("verify.log", log_text)):
        for kind in ("START", "HEARTBEAT", "END"):
            check(f"markers: {kind} present in {source_name}", f"[verify] " in text and f" {kind} " in text)
        check(f"markers: {source_name} is ASCII", text.isascii())


def test_env(tmp: Path) -> None:
    root = tmp / "env"
    root.mkdir()
    cmd = write_script(
        tmp,
        "env.py",
        "import os\n"
        "for k in ('MSBUILDDISABLENODEREUSE','DOTNET_CLI_USE_MSBUILD_SERVER','CALLER_KEY'):\n"
        "    print(k + '=' + os.environ.get(k, 'MISSING'))\n",
    )
    env = dict(os.environ)
    env["CALLER_KEY"] = "caller-value"
    result, _ = run(cmd, root, env=env)
    check(
        "env: forced keys and caller key reach the child",
        "MSBUILDDISABLENODEREUSE=1" in result.output
        and "DOTNET_CLI_USE_MSBUILD_SERVER=0" in result.output
        and "CALLER_KEY=caller-value" in result.output,
        result.output,
    )


def test_output(tmp: Path) -> None:
    root = tmp / "output"
    root.mkdir()
    cmd = write_script(
        tmp,
        "both.py",
        "import sys\nprint('to-stdout')\nprint('to-stderr', file=sys.stderr)\n",
    )
    result, _ = run(cmd, root)
    check(
        "output: stdout and stderr captured and output_path exists",
        "to-stdout" in result.output
        and "to-stderr" in result.output
        and result.output_path is not None
        and result.output_path.exists(),
    )


def test_decoding(tmp: Path) -> None:
    root = tmp / "decode"
    root.mkdir()
    cmd = write_script(
        tmp,
        "badbytes.py",
        "import sys\nsys.stdout.buffer.write(b'ok \\xff\\xfe end')\nsys.stdout.flush()\n",
    )
    result, _ = run(cmd, root)
    check("decoding: invalid UTF-8 is replaced, no exception", "�" in result.output)


def test_launch_failure(tmp: Path) -> None:
    root = tmp / "launch"
    root.mkdir()
    result, _ = run("echo hi", root, cwd=tmp / "does-not-exist")
    check(
        "launch failure: exit_code None and not timed_out",
        result.exit_code is None and result.timed_out is False,
    )


def test_programmer_errors(tmp: Path) -> None:
    root = tmp / "programmer"
    root.mkdir()
    for name, overrides in (("cwd=None", {"cwd": None}), ("bogus shell_mode", {"shell_mode": "bogus"})):
        try:
            run("echo hi", root, **overrides)
        except ValueError:
            check(f"programmer error: {name} raises ValueError", True)
        else:
            check(f"programmer error: {name} raises ValueError", False, "no exception")


def test_live_log_failure(tmp: Path) -> None:
    root = tmp / "livelog"
    (root / ".scratch" / "verify" / "verify.log").mkdir(parents=True)
    cmd = write_script(tmp, "ok.py", "print('fine')")
    result, _ = run(cmd, root)
    check("live-log failure: passing run still passes", result.exit_code == 0, str(result.exit_code))


def test_status_row(tmp: Path) -> None:
    root = tmp / "status"
    root.mkdir()
    status_file = root / "status.md"
    status_file.write_text(
        _status.render_initial("T", "D", "2026-10-14T10:00:00Z", "main", slug="s", branch="b"),
        encoding="utf-8",
    )
    cmd = write_script(tmp, "ok2.py", "print('fine')")
    run(cmd, root, status_path=status_file)
    run(cmd, root, status_path=status_file)
    rows = _status.read_verify_log_rows(status_file)
    check(
        "status row: one row per run",
        len(rows) == 2 and "t-label" in rows[0] and "exit=0" in rows[0] and "first_run=true" in rows[0]
        and "first_run=false" in rows[1],
        repr(rows),
    )

    root2 = tmp / "status-none"
    root2.mkdir()
    _, stderr_text = run(cmd, root2, status_path=None)
    check(
        "status row: None status_path prints the skip note",
        "no status.md -- Verify log row skipped for t-label" in stderr_text,
    )


def test_shell_modes() -> None:
    cmd = "PYTHONPATH= uv run foo"
    with unittest.mock.patch("_verify_run.os") as mock_os, unittest.mock.patch("_verify_run.shutil") as mock_shutil:
        mock_os.name = "nt"
        mock_shutil.which.return_value = "/usr/bin/bash"
        args, kwargs = _verify_run._posix_shell_run_args(cmd)
        check(
            "posix-shell-args: Windows with bash",
            args == ["/usr/bin/bash", "-c", cmd] and kwargs == {},
        )
    with unittest.mock.patch("_verify_run.os") as mock_os, unittest.mock.patch("_verify_run.shutil") as mock_shutil:
        mock_os.name = "nt"
        mock_shutil.which.return_value = None
        args, kwargs = _verify_run._posix_shell_run_args(cmd)
        check("posix-shell-args: Windows without bash", args == cmd and kwargs == {"shell": True})
    with unittest.mock.patch("_verify_run.os") as mock_os:
        mock_os.name = "posix"
        args, kwargs = _verify_run._posix_shell_run_args(cmd)
        check("posix-shell-args: POSIX", args == cmd and kwargs == {"shell": True})

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        fake = unittest.mock.MagicMock()
        fake.wait.return_value = 0
        fake.returncode = 0
        fake.pid = 1
        with unittest.mock.patch.object(_verify_run.subprocess, "Popen", return_value=fake) as popen:
            run("some native command", root, shell_mode="native")
        call = popen.call_args
        check(
            "native shell mode: Popen called with the raw command and shell=True",
            call.args == ("some native command",) and call.kwargs.get("shell") is True,
            repr(call),
        )


def test_timeout_seconds() -> None:
    check("timeout_seconds: absent key -> 1200.0", _verify_run.timeout_seconds({}) == 1200.0)
    check(
        "timeout_seconds: pipeline without key -> 1200.0",
        _verify_run.timeout_seconds({"pipeline": {}}) == 1200.0,
    )
    check(
        "timeout_seconds: 5 -> 300.0",
        _verify_run.timeout_seconds({"pipeline": {"verify_timeout_minutes": 5}}) == 300.0,
    )
    for bad in (0, -1, "x", None, True):
        try:
            _verify_run.timeout_seconds({"pipeline": {"verify_timeout_minutes": bad}})
        except ValueError as exc:
            check(
                f"timeout_seconds: {bad!r} raises ValueError naming the key",
                "pipeline.verify_timeout_minutes" in str(exc),
                str(exc),
            )
        else:
            check(f"timeout_seconds: {bad!r} raises ValueError", False, "no exception")


def test_resolve_status_path(tmp: Path) -> None:
    root = tmp / "resolve"
    (root / "_mill").mkdir(parents=True)
    cfg = {"paths": {"status_md": "_mill/status.md"}}
    check("resolve_status_path: missing file -> None", _verify_run.resolve_status_path(root, cfg) is None)
    (root / "_mill" / "status.md").write_text("x", encoding="utf-8")
    resolved = _verify_run.resolve_status_path(root, cfg)
    check(
        "resolve_status_path: existing file -> path",
        resolved is not None and resolved.resolve() == (root / "_mill" / "status.md").resolve(),
    )
    check("resolve_status_path: missing paths key -> None", _verify_run.resolve_status_path(root, {}) is None)


def test_summary_and_helpers() -> None:
    record = _verify_run.VerifyRun(
        label="lbl", cmd="c", cwd=Path("."), exit_code=1, wall_s=1.26, first_run=True,
        timed_out=False, output="o", output_path=Path("p.out"), timeout_s=90.0,
    )
    check(
        "VerifyRun.summary: fields and rounding",
        record.summary()
        == {"label": "lbl", "cmd": "c", "exit_code": 1, "wall_s": 1.3, "first_run": True, "timed_out": False},
        repr(record.summary()),
    )
    check(
        "timeout_prefix and output_suffix",
        _verify_run.timeout_prefix(record) == "[verify timed out after 90s: lbl] "
        and _verify_run.output_suffix(record) == f"\n[verify output: {Path('p.out')}]",
    )
    record.output_path = None
    check("output_suffix: empty without output_path", _verify_run.output_suffix(record) == "")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        test_pipe_trap(tmp)
        test_timeout(tmp)
        test_first_run_marker(tmp)
        test_markers(tmp)
        test_env(tmp)
        test_output(tmp)
        test_decoding(tmp)
        test_launch_failure(tmp)
        test_programmer_errors(tmp)
        test_live_log_failure(tmp)
        test_status_row(tmp)
        test_shell_modes()
        test_timeout_seconds()
        test_resolve_status_path(tmp)
        test_summary_and_helpers()
    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _verify_run unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
