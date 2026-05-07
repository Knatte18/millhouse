"""Unit tests for plugins/mill/scripts/millpy-bg.py (launcher and worker modes)."""
from __future__ import annotations

import importlib.util
import io
import re
import sys
import tempfile
import unittest.mock
import warnings
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

_BG_PY = HUB / "plugins" / "mill" / "scripts" / "millpy-bg.py"


def _load_bg_module(worker_mode: bool):
    name = "millpy_bg_worker" if worker_mode else "millpy_bg_launcher"
    saved_argv = sys.argv[:]
    sys.argv = [str(_BG_PY)] + (["--_worker"] if worker_mode else [])
    try:
        spec = importlib.util.spec_from_file_location(name, str(_BG_PY))
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except SystemExit as exc:
            if exc.code != 0:
                raise
        return mod
    finally:
        sys.argv = saved_argv


_launcher_mod = _load_bg_module(worker_mode=False)
_launcher_main = _launcher_mod._launcher_main

_worker_mod = _load_bg_module(worker_mode=True)
_worker_main = _worker_mod._worker_main


def _mock_git_run_result(git_root: str) -> unittest.mock.MagicMock:
    return unittest.mock.MagicMock(returncode=0, stdout=git_root + "\n", stderr="")


def _mock_popen_instance(pid: int = 12345) -> unittest.mock.MagicMock:
    m = unittest.mock.MagicMock()
    m.pid = pid
    return m


def main() -> int:
    failures: list[str] = []

    # ── Launcher mode tests ──────────────────────────────────────────────────

    # (a) log path format
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            with unittest.mock.patch.object(
                _launcher_mod.subprocess, "run",
                return_value=_mock_git_run_result(tmpdir),
            ), unittest.mock.patch.object(
                _launcher_mod.subprocess, "Popen",
                return_value=_mock_popen_instance(),
            ):
                buf = io.StringIO()
                with unittest.mock.patch("sys.stdout", buf):
                    ret = _launcher_main(["--slug", "myslug", "--", "echo", "hi"])

                assert ret == 0, f"expected 0, got {ret}"
                line = buf.getvalue().strip()
                assert re.match(r"pid=\d+ log=", line), f"output format wrong: {line!r}"
                log_path_str = line.split(" log=", 1)[1]
                log_path = Path(log_path_str)
                assert log_path.parent.name == ".scratch", f"not under .scratch/: {log_path}"
                assert re.match(r"bg-\d{8}-\d{6}-myslug\.log$", log_path.name), (
                    f"filename format wrong: {log_path.name!r}"
                )
        print("PASS (a): log path format correct")
    except AssertionError as exc:
        failures.append(f"FAIL (a) log path format: {exc}")
    except Exception as exc:
        failures.append(f"FAIL (a) log path format ({type(exc).__name__}): {exc}")

    # (b) .scratch/ created
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            scratch = Path(tmpdir) / ".scratch"
            assert not scratch.exists(), ".scratch/ should not exist before call"
            with unittest.mock.patch.object(
                _launcher_mod.subprocess, "run",
                return_value=_mock_git_run_result(tmpdir),
            ), unittest.mock.patch.object(
                _launcher_mod.subprocess, "Popen",
                return_value=_mock_popen_instance(),
            ):
                with unittest.mock.patch("sys.stdout", io.StringIO()):
                    _launcher_main(["--slug", "myslug", "--", "echo", "hi"])

            assert scratch.exists() and scratch.is_dir(), f".scratch/ not created in {tmpdir}"
        print("PASS (b): .scratch/ created by launcher")
    except AssertionError as exc:
        failures.append(f"FAIL (b) .scratch/ created: {exc}")
    except Exception as exc:
        failures.append(f"FAIL (b) .scratch/ created ({type(exc).__name__}): {exc}")

    # (c) stdout is exactly one non-empty line
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            with unittest.mock.patch.object(
                _launcher_mod.subprocess, "run",
                return_value=_mock_git_run_result(tmpdir),
            ), unittest.mock.patch.object(
                _launcher_mod.subprocess, "Popen",
                return_value=_mock_popen_instance(pid=42),
            ):
                buf = io.StringIO()
                with unittest.mock.patch("sys.stdout", buf):
                    _launcher_main(["--slug", "myslug", "--", "echo", "hi"])

                non_empty = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
                assert len(non_empty) == 1, (
                    f"expected 1 non-empty line, got {len(non_empty)}: {buf.getvalue()!r}"
                )
        print("PASS (c): stdout is exactly one non-empty line")
    except AssertionError as exc:
        failures.append(f"FAIL (c) stdout one line: {exc}")
    except Exception as exc:
        failures.append(f"FAIL (c) stdout one line ({type(exc).__name__}): {exc}")

    # (d) Windows creationflags
    try:
        expected_flags = 0x00000008 | 0x00000200 | 0x01000000  # = 0x01000208
        with tempfile.TemporaryDirectory() as tmpdir:
            with unittest.mock.patch.object(_launcher_mod.os, "name", "nt"), \
                 unittest.mock.patch.object(
                     _launcher_mod.subprocess, "run",
                     return_value=_mock_git_run_result(tmpdir),
                 ), unittest.mock.patch.object(
                     _launcher_mod.subprocess, "Popen",
                     return_value=_mock_popen_instance(pid=1),
                 ) as mock_popen_cls:
                with unittest.mock.patch("sys.stdout", io.StringIO()):
                    _launcher_main(["--slug", "win-test", "--", "echo", "hi"])

                call_kwargs = mock_popen_cls.call_args[1]
                assert "creationflags" in call_kwargs, "creationflags missing from Popen kwargs"
                assert call_kwargs["creationflags"] == expected_flags, (
                    f"creationflags={call_kwargs['creationflags']:#010x}, "
                    f"expected {expected_flags:#010x}"
                )
                assert "start_new_session" not in call_kwargs, (
                    "start_new_session must not be set on nt"
                )
        print(f"PASS (d): Windows creationflags = {expected_flags:#010x}")
    except AssertionError as exc:
        failures.append(f"FAIL (d) Windows flags: {exc}")
    except Exception as exc:
        failures.append(f"FAIL (d) Windows flags ({type(exc).__name__}): {exc}")

    # (e) POSIX start_new_session, no creationflags
    try:
        # Capture the concrete platform Path class (WindowsPath on Windows) so that
        # mocking os.name="posix" does not cause pathlib.Path.__new__ to dispatch to
        # PosixPath, which cannot be instantiated on Windows.
        _concrete_path_cls = type(_launcher_mod.Path("."))
        with tempfile.TemporaryDirectory() as tmpdir:
            with unittest.mock.patch.object(_launcher_mod.os, "name", "posix"), \
                 unittest.mock.patch.object(_launcher_mod, "Path", _concrete_path_cls), \
                 unittest.mock.patch.object(
                     _launcher_mod.subprocess, "run",
                     return_value=_mock_git_run_result(tmpdir),
                 ), unittest.mock.patch.object(
                     _launcher_mod.subprocess, "Popen",
                     return_value=_mock_popen_instance(pid=2),
                 ) as mock_popen_cls:
                with unittest.mock.patch("sys.stdout", io.StringIO()):
                    _launcher_main(["--slug", "posix-test", "--", "echo", "hi"])

                call_kwargs = mock_popen_cls.call_args[1]
                assert call_kwargs.get("start_new_session") is True, (
                    f"start_new_session should be True, "
                    f"got {call_kwargs.get('start_new_session')!r}"
                )
                assert "creationflags" not in call_kwargs, (
                    "creationflags must not be set on posix"
                )
        print("PASS (e): POSIX start_new_session=True, no creationflags")
    except AssertionError as exc:
        failures.append(f"FAIL (e) POSIX flags: {exc}")
    except Exception as exc:
        failures.append(f"FAIL (e) POSIX flags ({type(exc).__name__}): {exc}")

    # (f) missing --slug returns 1
    try:
        with unittest.mock.patch("sys.stderr", io.StringIO()):
            ret = _launcher_main(["--", "echo", "hi"])
        assert ret == 1, f"expected 1, got {ret}"
        print("PASS (f): missing --slug returns 1")
    except AssertionError as exc:
        failures.append(f"FAIL (f) missing --slug: {exc}")
    except Exception as exc:
        failures.append(f"FAIL (f) missing --slug ({type(exc).__name__}): {exc}")

    # (g) missing -- returns 1
    try:
        with unittest.mock.patch("sys.stderr", io.StringIO()):
            ret = _launcher_main(["--slug", "x"])
        assert ret == 1, f"expected 1, got {ret}"
        print("PASS (g): missing -- separator returns 1")
    except AssertionError as exc:
        failures.append(f"FAIL (g) missing --: {exc}")
    except Exception as exc:
        failures.append(f"FAIL (g) missing -- ({type(exc).__name__}): {exc}")

    # (m) no DeprecationWarning from utcnow
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            with unittest.mock.patch.object(
                _launcher_mod.subprocess, "run",
                return_value=_mock_git_run_result(tmpdir),
            ), unittest.mock.patch.object(
                _launcher_mod.subprocess, "Popen",
                return_value=_mock_popen_instance(),
            ):
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    with unittest.mock.patch("sys.stdout", io.StringIO()):
                        ret = _launcher_main(["--slug", "utctest", "--", "echo", "hi"])
                utcnow_warnings = [
                    x for x in w
                    if x.category is DeprecationWarning and "utcnow" in str(x.message)
                ]
                assert ret == 0, f"expected 0, got {ret}"
                assert len(utcnow_warnings) == 0, (
                    f"DeprecationWarning about utcnow emitted: {utcnow_warnings}"
                )
        print("PASS (m): no DeprecationWarning from utcnow in launcher")
    except AssertionError as exc:
        failures.append(f"FAIL (m) utcnow warning: {exc}")
    except Exception as exc:
        failures.append(f"FAIL (m) utcnow warning ({type(exc).__name__}): {exc}")

    # ── Worker mode tests ────────────────────────────────────────────────────

    # (h) output captured to log + (i) sentinel written on success
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test.log"
            ret = _worker_main(
                ["--log", str(log_path), "--", sys.executable, "-c", "print('hello')"]
            )
            assert ret == 0, f"expected 0, got {ret}"
            assert log_path.exists(), "log file not created"
            log_text = log_path.read_text(encoding="utf-8")
            assert "hello" in log_text, f"'hello' not in log: {log_text!r}"
        print("PASS (h): worker captures command output to log file")

        stripped = log_text.rstrip()
        assert stripped.endswith("[mill-bg] EXIT 0"), (
            f"log does not end with '[mill-bg] EXIT 0'; last 60 chars: {stripped[-60:]!r}"
        )
        print("PASS (i): sentinel [mill-bg] EXIT 0 written on success")
    except AssertionError as exc:
        failures.append(f"FAIL (h)/(i) output/sentinel: {exc}")
    except Exception as exc:
        failures.append(f"FAIL (h)/(i) output/sentinel ({type(exc).__name__}): {exc}")

    # (j) non-zero exit code written in sentinel
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test-exit3.log"
            ret = _worker_main([
                "--log", str(log_path), "--",
                sys.executable, "-c", "import sys; sys.exit(3)",
            ])
            assert ret == 0, f"_worker_main itself should return 0, got {ret}"
            log_text = log_path.read_text(encoding="utf-8")
            assert "[mill-bg] EXIT 3" in log_text, (
                f"'[mill-bg] EXIT 3' not in log: {log_text!r}"
            )
        print("PASS (j): non-zero exit code written as [mill-bg] EXIT 3")
    except AssertionError as exc:
        failures.append(f"FAIL (j) non-zero exit code: {exc}")
    except Exception as exc:
        failures.append(f"FAIL (j) non-zero exit code ({type(exc).__name__}): {exc}")

    # (k) missing --log returns 1
    try:
        with unittest.mock.patch("sys.stderr", io.StringIO()):
            ret = _worker_main(["--", "echo", "hi"])
        assert ret == 1, f"expected 1, got {ret}"
        print("PASS (k): missing --log returns 1")
    except AssertionError as exc:
        failures.append(f"FAIL (k) missing --log: {exc}")
    except Exception as exc:
        failures.append(f"FAIL (k) missing --log ({type(exc).__name__}): {exc}")

    # (l) missing command after -- returns 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "unused.log"
            with unittest.mock.patch("sys.stderr", io.StringIO()):
                ret = _worker_main(["--log", str(log_path), "--"])
            assert ret == 1, f"expected 1, got {ret}"
        print("PASS (l): missing command after -- returns 1")
    except AssertionError as exc:
        failures.append(f"FAIL (l) missing command: {exc}")
    except Exception as exc:
        failures.append(f"FAIL (l) missing command ({type(exc).__name__}): {exc}")

    if failures:
        for msg in failures:
            print(msg, file=sys.stderr)
        return 1

    print("All millpy-bg unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
