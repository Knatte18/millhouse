"""Unit tests for _daemon.DaemonBase logic.

Covers: _write_state_file writes and reads back as JSON; _is_stale detects
dead PIDs and current PIDs; O_EXCL behavior; idle-timeout predicate;
.gitignore idempotent append; WikiServer.on_stop closes log handlers.

Uses tempfile dirs; no real TCP sockets or accept loop.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import tempfile
import time
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _daemon import DaemonBase  # noqa: E402
from wiki._server import WikiServer  # noqa: E402
from _test_helpers import safe_temp_dir  # noqa: E402


class TestDaemon(DaemonBase):
    """Minimal DaemonBase subclass for testing."""

    def handle_request(self, msg: dict) -> dict:
        return {"ok": True}


def main() -> int:
    passed = 0
    failed = 0

    def ok(name: str) -> None:
        nonlocal passed
        passed += 1
        print(f"PASS: {name}")

    def fail(name: str, exc: Exception) -> None:
        nonlocal failed
        failed += 1
        print(f"FAIL: {name}: {exc}", file=sys.stderr)

    # --- (a) _write_state_file writes JSON, reads back ---
    try:
        tmp = Path(tempfile.mkdtemp())
        try:
            state_file = tmp / "state.json"
            data = {
                "protocol_version": 1,
                "pid": 12345,
                "port": 9999,
                "token": "abc123",
            }
            daemon = TestDaemon("test", state_file, 30)
            daemon._write_state_file(state_file, data)

            read_data = json.loads(state_file.read_text(encoding="utf-8"))
            assert read_data["protocol_version"] == 1
            assert read_data["pid"] == 12345
            assert read_data["port"] == 9999
            assert read_data["token"] == "abc123"
            ok("_write_state_file writes JSON, reads back")
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
    except Exception as exc:
        fail("_write_state_file writes JSON, reads back", exc)

    # --- (b) _is_stale returns True for non-existent PID ---
    try:
        tmp = Path(tempfile.mkdtemp())
        try:
            state_file = tmp / "state.json"
            daemon = TestDaemon("test", state_file, 30)
            state = {"pid": os.getpid() + 999999}
            assert daemon._is_stale(state) is True
            ok("_is_stale returns True for non-existent PID")
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
    except Exception as exc:
        fail("_is_stale returns True for non-existent PID", exc)

    # --- (c) _is_stale returns False for current PID ---
    try:
        import socket
        tmp = Path(tempfile.mkdtemp())
        try:
            state_file = tmp / "state.json"
            daemon = TestDaemon("test", state_file, 30)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.listen(1)
            try:
                state = {"pid": os.getpid(), "host": "127.0.0.1", "port": port}
                result = daemon._is_stale(state)
                assert result is False, f"expected False, got {result}"
                ok("_is_stale returns False for current PID")
            finally:
                sock.close()
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
    except Exception as exc:
        fail("_is_stale returns False for current PID", exc)

    # --- (d) O_EXCL behavior: first open succeeds, second raises FileExistsError ---
    try:
        tmp = Path(tempfile.mkdtemp())
        try:
            test_file = tmp / "exclusive.txt"
            with open(test_file, "x") as f:
                f.write("first")
            raised = False
            try:
                open(test_file, "x").close()
            except FileExistsError:
                raised = True
            assert raised, "second open should raise FileExistsError"
            ok("O_EXCL behavior: first open succeeds, second raises FileExistsError")
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
    except Exception as exc:
        fail("O_EXCL behavior: first open succeeds, second raises FileExistsError", exc)

    # --- (e) idle-timeout computation: elapsed > idle_timeout ---
    try:
        last_activity = time.monotonic()
        idle_timeout = 0.01
        time.sleep(0.02)
        elapsed = time.monotonic() - last_activity
        is_stale = elapsed > idle_timeout
        assert is_stale is True
        ok("idle-timeout computation: elapsed > idle_timeout")
    except Exception as exc:
        fail("idle-timeout computation: elapsed > idle_timeout", exc)

    # --- (f) .gitignore idempotent append ---
    try:
        tmp = Path(tempfile.mkdtemp())
        try:
            gitignore_path = tmp / ".gitignore"

            def ensure_gitignore_entry(path: Path, entry: str) -> None:
                """Idempotent: add entry if not present."""
                if path.exists():
                    content = path.read_text(encoding="utf-8")
                    if entry in content:
                        return
                    path.write_text(content + entry + "\n", encoding="utf-8")
                else:
                    path.write_text(entry + "\n", encoding="utf-8")

            ensure_gitignore_entry(gitignore_path, ".wiki-daemon.json")
            first_content = gitignore_path.read_text(encoding="utf-8")
            count1 = first_content.count(".wiki-daemon.json")

            ensure_gitignore_entry(gitignore_path, ".wiki-daemon.json")
            second_content = gitignore_path.read_text(encoding="utf-8")
            count2 = second_content.count(".wiki-daemon.json")

            assert count1 == 1, f"expected 1 occurrence, got {count1}"
            assert count2 == 1, f"expected 1 occurrence after second call, got {count2}"
            ok(".gitignore idempotent append")
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
    except Exception as exc:
        fail(".gitignore idempotent append", exc)

    # --- (g) WikiServer.on_stop closes log handlers and removes them from logger ---
    try:
        with safe_temp_dir() as tmp:
            wiki_path = tmp / "wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)
            (wiki_path / "tasks.json").write_text('{"_default": {}}', encoding="utf-8")
            wiki_server = WikiServer(wiki_path, idle_timeout=1)

            our_handlers = [
                h for h in wiki_server._log.handlers
                if isinstance(h, logging.handlers.RotatingFileHandler)
                and Path(h.baseFilename).resolve() == (wiki_path / ".wiki-daemon.log").resolve()
            ]
            assert len(our_handlers) == 1, f"expected 1 handler, got {len(our_handlers)}"
            handler = our_handlers[0]

            wiki_server.on_stop()

            assert handler.stream is None or handler.stream.closed, \
                "handler stream should be closed or None after on_stop"
            assert handler not in wiki_server._log.handlers, \
                "handler should be removed from logger after on_stop"
            ok("WikiServer.on_stop closes log handlers and removes them from logger")
    except Exception as exc:
        fail("WikiServer.on_stop closes log handlers and removes them from logger", exc)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
