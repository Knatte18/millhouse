"""Unit test for plugins/mill/scripts/_subprocess_util.py.

Covers: happy-path, timeout-kill path, breadcrumb format, check= behaviour.
Deeper kill verification (parent + children both gone) lives in integration_tests/.
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

from _subprocess_util import _GRACE_SECONDS, popen_detached, run  # noqa: E402

# Tests (d) and (e) use a small_delta for timeout wall-time budget
_SMALL_DELTA = 5


def main() -> int:
    failures: list[str] = []

    # (c) normal-completion regression
    try:
        result = run(["git", "--version"])
        assert result.returncode == 0, f"git --version exit {result.returncode}"
        assert "git version" in result.stdout, f"unexpected stdout: {result.stdout!r}"
        assert isinstance(result.stdout, str), "stdout must be str"
        print(f"PASS (c): _subprocess_util.run('git --version') -> {result.stdout.strip()}")
    except AssertionError as exc:
        failures.append(f"FAIL (c) normal-completion: {exc}")

    # (a) timeout fires + (b) breadcrumb format
    # Deep tree-kill verification is deferred to integration_tests/
    try:
        buf = io.StringIO()
        deadline = time.monotonic() + 2.0 + _GRACE_SECONDS + _SMALL_DELTA
        with contextlib.redirect_stderr(buf):
            try:
                run(
                    [sys.executable, "-c", "import time; time.sleep(60)"],
                    timeout=2.0,
                )
                failures.append("FAIL (a) timeout-fires: expected TimeoutExpired, got nothing")
            except subprocess.TimeoutExpired:
                pass
        assert time.monotonic() < deadline, (
            f"timeout + kill exceeded wall-time budget of {2.0 + _GRACE_SECONDS + _SMALL_DELTA}s"
        )
        print("PASS (a): TimeoutExpired raised within wall-time budget")

        # (b) breadcrumb format check using the stderr captured above
        stderr_out = buf.getvalue()
        assert "[subprocess] spawn argv=" in stderr_out, (
            f"spawn breadcrumb missing from stderr:\n{stderr_out!r}"
        )
        assert "[subprocess] exit code=timeout duration=" in stderr_out, (
            f"timeout exit breadcrumb missing from stderr:\n{stderr_out!r}"
        )
        print("PASS (b): breadcrumb format correct")
    except AssertionError as exc:
        failures.append(f"FAIL (a)/(b) timeout/breadcrumb: {exc}")

    # (d) check=True raises CalledProcessError
    try:
        run(
            [sys.executable, "-c", "import sys; sys.exit(7)"],
            check=True,
        )
        failures.append("FAIL (d) check=True: expected CalledProcessError, got nothing")
    except subprocess.CalledProcessError as exc:
        assert exc.returncode == 7, f"expected returncode 7, got {exc.returncode}"
        print("PASS (d): check=True raises CalledProcessError with returncode=7")
    except AssertionError as exc:
        failures.append(f"FAIL (d) check=True: {exc}")

    # (e) check=False returns CompletedProcess with non-zero returncode
    try:
        result = run(
            [sys.executable, "-c", "import sys; sys.exit(7)"],
            check=False,
        )
        assert result.returncode == 7, f"expected returncode 7, got {result.returncode}"
        print("PASS (e): check=False returns CompletedProcess with returncode=7")
    except AssertionError as exc:
        failures.append(f"FAIL (e) check=False: {exc}")

    # (f) run with stdout override writes to file
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".txt")
        os.close(tmp_fd)
        with open(tmp_path, "w", encoding="utf-8") as tmp_f:
            result = run(
                [sys.executable, "-c", "import sys; sys.stdout.write('hello')"],
                stdout=tmp_f,
            )
        with open(tmp_path, encoding="utf-8") as f:
            content = f.read()
        os.unlink(tmp_path)
        assert "hello" in content, f"expected 'hello' in file, got {content!r}"
        assert result.returncode == 0, f"expected returncode 0, got {result.returncode}"
        assert result.stdout == "", f"expected result.stdout == '', got {result.stdout!r}"
        print("PASS (f): run with stdout override writes to file")
    except AssertionError as exc:
        failures.append(f"FAIL (f) run-stdout-override: {exc}")

    # (g) run with stderr-to-stdout redirect
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".txt")
        os.close(tmp_fd)
        with open(tmp_path, "w", encoding="utf-8") as tmp_f:
            result = run(
                [sys.executable, "-c", "import sys; sys.stderr.write('err-content')"],
                stdout=tmp_f,
                stderr=subprocess.STDOUT,
            )
        with open(tmp_path, encoding="utf-8") as f:
            content = f.read()
        os.unlink(tmp_path)
        assert "err-content" in content, f"expected 'err-content' in file, got {content!r}"
        assert result.stderr == "", f"expected result.stderr == '', got {result.stderr!r}"
        print("PASS (g): run with stderr-to-stdout redirect")
    except AssertionError as exc:
        failures.append(f"FAIL (g) run-stderr-to-stdout: {exc}")

    # (h) run default behaviour unchanged
    try:
        result = run(["git", "--version"])
        assert result.stdout != "", f"expected non-empty stdout, got {result.stdout!r}"
        assert isinstance(result.stdout, str), f"expected str stdout, got {type(result.stdout)}"
        print(f"PASS (h): run default behaviour unchanged -> {result.stdout.strip()}")
    except AssertionError as exc:
        failures.append(f"FAIL (h) run-default-behaviour: {exc}")

    # (i) popen_detached returns Popen with pid
    try:
        proc = popen_detached(
            [sys.executable, "-c", "pass"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        assert isinstance(proc, subprocess.Popen), f"expected Popen, got {type(proc)}"
        assert proc.pid > 0, f"expected positive pid, got {proc.pid}"
        proc.wait(timeout=5)
        assert proc.returncode == 0, f"expected returncode 0, got {proc.returncode}"
        print(f"PASS (i): popen_detached returns Popen with pid={proc.pid}")
    except AssertionError as exc:
        failures.append(f"FAIL (i) popen_detached-popen-pid: {exc}")

    # (j) popen_detached injects PYTHONIOENCODING=utf-8
    try:
        tmp_fd, out_path = tempfile.mkstemp(suffix=".txt")
        os.close(tmp_fd)
        script = (
            "import os, sys\n"
            "with open(sys.argv[1], 'w') as f:\n"
            "    f.write(os.environ.get('PYTHONIOENCODING', '<missing>'))\n"
        )
        script_fd, script_path = tempfile.mkstemp(suffix=".py")
        os.write(script_fd, script.encode("utf-8"))
        os.close(script_fd)
        proc = popen_detached(
            [sys.executable, script_path, out_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        proc.wait(timeout=5)
        with open(out_path, encoding="utf-8") as f:
            result_text = f.read()
        os.unlink(out_path)
        os.unlink(script_path)
        assert "utf-8" in result_text, f"expected 'utf-8' in env output, got {result_text!r}"
        print("PASS (j): popen_detached injects PYTHONIOENCODING=utf-8")
    except AssertionError as exc:
        failures.append(f"FAIL (j) popen_detached-env-injection: {exc}")

    # (k) popen_detached creationflags on Windows
    if os.name != "nt":
        print("SKIP (k): not applicable on POSIX")
    else:
        try:
            with unittest.mock.patch.object(subprocess, "Popen") as mock_popen_cls:
                mock_popen_cls.return_value = unittest.mock.MagicMock(pid=42)
                popen_detached(
                    [sys.executable, "-c", "pass"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            call_kwargs = mock_popen_cls.call_args[1]
            expected_flags = (
                subprocess.CREATE_NO_WINDOW
                | subprocess.CREATE_NEW_PROCESS_GROUP
                | 0x01000000  # CREATE_BREAKAWAY_FROM_JOB
            )
            assert call_kwargs["creationflags"] == expected_flags, (
                f"expected creationflags={expected_flags:#010x}, "
                f"got {call_kwargs.get('creationflags'):#010x}"
            )
            print(f"PASS (k): popen_detached creationflags on Windows = {expected_flags:#010x}")
        except AssertionError as exc:
            failures.append(f"FAIL (k) popen_detached-creationflags: {exc}")

    # (l) popen_detached start_new_session on POSIX
    if os.name == "nt":
        print("SKIP (l): not applicable on Windows")
    else:
        try:
            with unittest.mock.patch.object(subprocess, "Popen") as mock_popen_cls:
                mock_popen_cls.return_value = unittest.mock.MagicMock(pid=99)
                popen_detached(
                    [sys.executable, "-c", "pass"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            call_kwargs = mock_popen_cls.call_args[1]
            assert call_kwargs.get("start_new_session") is True, (
                f"expected start_new_session=True, got {call_kwargs.get('start_new_session')!r}"
            )
            assert "creationflags" not in call_kwargs, (
                f"expected no creationflags on POSIX, got {call_kwargs.get('creationflags')}"
            )
            print("PASS (l): popen_detached start_new_session on POSIX")
        except AssertionError as exc:
            failures.append(f"FAIL (l) popen_detached-start-new-session: {exc}")

    if failures:
        for msg in failures:
            print(msg, file=sys.stderr)
        return 1

    print("All _subprocess_util unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
