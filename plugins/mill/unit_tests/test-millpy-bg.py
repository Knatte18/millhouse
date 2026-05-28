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


def _mock_validation_success() -> tuple:
    """Return context managers that mock validation to always succeed."""
    try:
        import _marker  # noqa: F401
        import _paths  # noqa: F401
        import _config  # noqa: F401

        mock_resolve_wiki = unittest.mock.MagicMock(return_value=Path("/fake/wiki"))
        mock_load_config = unittest.mock.MagicMock(return_value={"spawn": {"branch_prefix": ""}})
        mock_slug_from_branch = unittest.mock.MagicMock(return_value="test")

        return (
            unittest.mock.patch("_marker.slug_from_branch", mock_slug_from_branch),
            unittest.mock.patch("_paths.resolve_wiki_path", mock_resolve_wiki),
            unittest.mock.patch("_config.load_config", mock_load_config),
        )
    except ImportError:
        return (unittest.mock.nullcontext(), unittest.mock.nullcontext(), unittest.mock.nullcontext())


def main() -> int:
    failures: list[str] = []

    # ── Launcher mode tests ──────────────────────────────────────────────────

    # (a) log path format
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            mocks = _mock_validation_success()
            with unittest.mock.patch.object(
                _launcher_mod._subprocess_util, "run",
                return_value=_mock_git_run_result(tmpdir),
            ), unittest.mock.patch.object(
                _launcher_mod._subprocess_util, "popen_detached",
                return_value=_mock_popen_instance(),
            ), mocks[0], mocks[1], mocks[2]:
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
            mocks = _mock_validation_success()
            with unittest.mock.patch.object(
                _launcher_mod._subprocess_util, "run",
                return_value=_mock_git_run_result(tmpdir),
            ), unittest.mock.patch.object(
                _launcher_mod._subprocess_util, "popen_detached",
                return_value=_mock_popen_instance(),
            ), mocks[0], mocks[1], mocks[2]:
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
            mocks = _mock_validation_success()
            with unittest.mock.patch.object(
                _launcher_mod._subprocess_util, "run",
                return_value=_mock_git_run_result(tmpdir),
            ), unittest.mock.patch.object(
                _launcher_mod._subprocess_util, "popen_detached",
                return_value=_mock_popen_instance(pid=42),
            ), mocks[0], mocks[1], mocks[2]:
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

    # (d) Windows path forwards pid via popen_detached
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            mocks = _mock_validation_success()
            with unittest.mock.patch.object(_launcher_mod._subprocess_util.os, "name", "nt"), \
                 unittest.mock.patch.object(
                     _launcher_mod._subprocess_util, "run",
                     return_value=_mock_git_run_result(tmpdir),
                 ), unittest.mock.patch.object(
                     _launcher_mod._subprocess_util.subprocess, "Popen",
                     return_value=_mock_popen_instance(pid=1),
                 ) as mock_popen_cls, \
                 mocks[0], mocks[1], mocks[2]:
                buf = io.StringIO()
                with unittest.mock.patch("sys.stdout", buf):
                    _launcher_main(["--slug", "win-test", "--", "echo", "hi"])

                assert mock_popen_cls.call_count == 1, (
                    "popen_detached should call Popen exactly once"
                )
                assert "pid=1" in buf.getvalue(), (
                    f"pid=1 not found in output: {buf.getvalue()!r}"
                )
        print("PASS (d): Windows path forwards pid via popen_detached")
    except AssertionError as exc:
        failures.append(f"FAIL (d) Windows flags: {exc}")
    except Exception as exc:
        failures.append(f"FAIL (d) Windows flags ({type(exc).__name__}): {exc}")

    # (e) POSIX path forwards pid via popen_detached
    # Skipped on Windows: patching os.name='posix' globally breaks pathlib.Path.cwd()
    # because Python 3.13 refuses to instantiate PosixPath on a Windows host.
    import os as _os
    if _os.name == "nt":
        print("SKIP (e): POSIX flags test (Windows host — cannot mock os.name)")
    else:
        try:
            _concrete_path_cls = type(_launcher_mod.Path("."))
            mocks = _mock_validation_success()
            with tempfile.TemporaryDirectory() as tmpdir:
                with unittest.mock.patch.object(_launcher_mod._subprocess_util.os, "name", "posix"), \
                     unittest.mock.patch.object(_launcher_mod, "Path", _concrete_path_cls), \
                     unittest.mock.patch.object(
                         _launcher_mod._subprocess_util, "run",
                         return_value=_mock_git_run_result(tmpdir),
                     ), unittest.mock.patch.object(
                         _launcher_mod._subprocess_util.subprocess, "Popen",
                         return_value=_mock_popen_instance(pid=2),
                     ) as mock_popen_cls, \
                     mocks[0], mocks[1], mocks[2]:
                    buf = io.StringIO()
                    with unittest.mock.patch("sys.stdout", buf):
                        _launcher_main(["--slug", "posix-test", "--", "echo", "hi"])

                    assert mock_popen_cls.call_count == 1, (
                        "popen_detached should call Popen exactly once"
                    )
                    assert "pid=2" in buf.getvalue(), (
                        f"pid=2 not found in output: {buf.getvalue()!r}"
                    )
            print("PASS (e): POSIX path forwards pid via popen_detached")
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
            mocks = _mock_validation_success()
            with unittest.mock.patch.object(
                _launcher_mod._subprocess_util, "run",
                return_value=_mock_git_run_result(tmpdir),
            ), unittest.mock.patch.object(
                _launcher_mod._subprocess_util, "popen_detached",
                return_value=_mock_popen_instance(),
            ), mocks[0], mocks[1], mocks[2]:
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

    # (n) worker writes START sentinel as first log line
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test-start.log"
            ret = _worker_main(
                ["--log", str(log_path), "--", sys.executable, "-c", "print('hello')"]
            )
            assert ret == 0, f"expected 0, got {ret}"
            assert log_path.exists(), "log file not created"
            log_text = log_path.read_text(encoding="utf-8")
            lines = log_text.splitlines(keepends=True)
            assert lines, "log file is empty"
            start_pattern = re.compile(
                r"^\[mill-bg\] WORKER PID=\d+ START \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\n"
            )
            assert start_pattern.match(lines[0]), (
                f"first log line does not match START sentinel pattern: {lines[0]!r}"
            )
            assert "hello" in log_text, f"'hello' not in log: {log_text!r}"
            stripped = log_text.rstrip()
            assert stripped.endswith("[mill-bg] EXIT 0"), (
                f"log does not end with '[mill-bg] EXIT 0'; last 60 chars: {stripped[-60:]!r}"
            )
        print("PASS (n): worker writes START sentinel as first log line")
    except AssertionError as exc:
        failures.append(f"FAIL (n) START sentinel: {exc}")
    except Exception as exc:
        failures.append(f"FAIL (n) START sentinel ({type(exc).__name__}): {exc}")

    # (o) worker FileNotFoundError writes EXIT -1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test-raise.log"
            with unittest.mock.patch("subprocess.run", side_effect=FileNotFoundError("fake: no such file")):
                ret = _worker_main(["--log", str(log_path), "--", "fake-cmd"])
            assert ret == 1, f"expected 1, got {ret}"
            assert log_path.exists(), "log file not created"
            log_text = log_path.read_text(encoding="utf-8")
            assert "[mill-bg] EXIT -1" in log_text, f"'[mill-bg] EXIT -1' not in log: {log_text!r}"
        print("PASS (o): worker FileNotFoundError -> EXIT -1 written in log")
    except AssertionError as exc:
        failures.append(f"FAIL (o) worker-FileNotFoundError: {exc}")
    except Exception as exc:
        failures.append(f"FAIL (o) worker-FileNotFoundError ({type(exc).__name__}): {exc}")

    # (p) worker KeyboardInterrupt writes EXIT -1 via finally (re-raises after finally)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test-keyboard.log"
            try:
                with unittest.mock.patch("subprocess.run", side_effect=KeyboardInterrupt()):
                    ret = _worker_main(["--log", str(log_path), "--", "fake-cmd"])
            except KeyboardInterrupt:
                # Worker re-raises BaseException after finally completes
                pass
            assert log_path.exists(), "log file not created"
            log_text = log_path.read_text(encoding="utf-8")
            exit_lines = [ln for ln in log_text.splitlines() if "[mill-bg] EXIT" in ln]
            assert len(exit_lines) == 1, (
                f"expected exactly one EXIT line, got {len(exit_lines)}: {exit_lines}"
            )
            assert exit_lines[0] == "[mill-bg] EXIT -1", (
                f"expected EXIT -1, got: {exit_lines[0]!r}"
            )
        print("PASS (p): worker KeyboardInterrupt -> EXIT -1 written via finally, then re-raised")
    except AssertionError as exc:
        failures.append(f"FAIL (p) worker-KeyboardInterrupt: {exc}")
    except Exception as exc:
        failures.append(f"FAIL (p) worker-KeyboardInterrupt ({type(exc).__name__}): {exc}")

    if failures:
        for msg in failures:
            print(msg, file=sys.stderr)
        return 1

    print("All millpy-bg unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
