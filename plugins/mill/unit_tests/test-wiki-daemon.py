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

import _safe_rmtree  # noqa: E402
from unittest.mock import patch, MagicMock  # noqa: E402
from _daemon import DaemonBase  # noqa: E402
from wiki._server import WikiServer  # noqa: E402
from wiki import PROTOCOL_VERSION, WikiStartupError, OP_SET_DEPS, OP_MIGRATE_DEPS, OP_LIST_TASKS_BRIEF, OP_REMOVE_TASK, FIELD_OK, FIELD_OP  # noqa: E402
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
            _safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)
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
            _safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)
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
            _safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)
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
            _safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)
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
            _safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)
    except Exception as exc:
        fail(".gitignore idempotent append", exc)

    # --- (g) WikiServer.on_stop closes log handlers and removes them from logger ---
    try:
        with safe_temp_dir() as tmp:
            wiki_path = tmp / "wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)
            (wiki_path / "tasks.json").write_text('{"_default": {}}', encoding="utf-8")
            # Force the production code path: SKIP_GIT=1 swaps RotatingFileHandler
            # for NullHandler (see _server.py), which is what the rest of the
            # suite uses but not what this test asserts on.
            prev_skip = os.environ.pop("WIKI_DAEMON_SKIP_GIT", None)
            try:
                wiki_server = WikiServer(wiki_path, idle_timeout=1)
            finally:
                if prev_skip is not None:
                    os.environ["WIKI_DAEMON_SKIP_GIT"] = prev_skip

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

    # --- (h) _ensure_daemon stale-port-reuse: OSError on health check triggers respawn ---
    try:
        from wiki import _client
        tmp = Path(tempfile.mkdtemp())
        try:
            wiki_path = tmp / "wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)
            (wiki_path / "tasks.json").write_text('{"_default": {}}', encoding="utf-8")

            state_file = wiki_path / ".wiki-daemon.json"
            state = {
                "protocol_version": PROTOCOL_VERSION,
                "pid": os.getpid() + 999999,
                "host": "127.0.0.1",
                "port": 9999,
                "token": "test-token",
            }
            state_file.write_text(json.dumps(state), encoding="utf-8")

            with patch("wiki._client.socket.create_connection") as mock_create_conn, \
                 patch("wiki._client._connect_send_recv") as mock_send_recv, \
                 patch("wiki._client._spawn_server") as mock_spawn, \
                 patch("wiki._client._is_stale") as mock_is_stale, \
                 patch("wiki._client.SPAWN_TIMEOUT", 0.01):

                mock_create_conn.return_value = MagicMock(close=MagicMock())
                mock_send_recv.side_effect = OSError("connection failed")
                mock_is_stale.return_value = True

                try:
                    _client._ensure_daemon(wiki_path)
                    fail("_ensure_daemon stale-port-reuse: OSError on health check triggers respawn",
                         Exception("expected WikiStartupError"))
                except WikiStartupError:
                    assert not state_file.exists(), "state file should be unlinked"
                    assert mock_spawn.call_count == 1, f"spawn_server called {mock_spawn.call_count} times, expected 1"
                    ok("_ensure_daemon stale-port-reuse: OSError on health check triggers respawn")
        finally:
            _safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)
    except Exception as exc:
        fail("_ensure_daemon stale-port-reuse: OSError on health check triggers respawn", exc)

    # --- (i) _ensure_daemon non-ok-health-response: bad response triggers respawn ---
    try:
        from wiki import _client, FIELD_OK, FIELD_ERROR
        tmp = Path(tempfile.mkdtemp())
        try:
            wiki_path = tmp / "wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)
            (wiki_path / "tasks.json").write_text('{"_default": {}}', encoding="utf-8")

            state_file = wiki_path / ".wiki-daemon.json"
            state = {
                "protocol_version": PROTOCOL_VERSION,
                "pid": os.getpid() + 999999,
                "host": "127.0.0.1",
                "port": 9999,
                "token": "test-token",
            }
            state_file.write_text(json.dumps(state), encoding="utf-8")

            with patch("wiki._client.socket.create_connection") as mock_create_conn, \
                 patch("wiki._client._connect_send_recv") as mock_send_recv, \
                 patch("wiki._client._spawn_server") as mock_spawn, \
                 patch("wiki._client._is_stale") as mock_is_stale, \
                 patch("wiki._client.SPAWN_TIMEOUT", 0.01):

                mock_create_conn.return_value = MagicMock(close=MagicMock())
                mock_send_recv.return_value = {FIELD_OK: False, FIELD_ERROR: "test"}
                mock_is_stale.return_value = True

                try:
                    _client._ensure_daemon(wiki_path)
                    fail("_ensure_daemon non-ok-health-response: bad response triggers respawn",
                         Exception("expected WikiStartupError"))
                except WikiStartupError:
                    assert not state_file.exists(), "state file should be unlinked"
                    assert mock_spawn.call_count == 1, f"spawn_server called {mock_spawn.call_count} times, expected 1"
                    ok("_ensure_daemon non-ok-health-response: bad response triggers respawn")
        finally:
            _safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)
    except Exception as exc:
        fail("_ensure_daemon non-ok-health-response: bad response triggers respawn", exc)

    # --- (j) _ensure_daemon successful-health: returns tuple without respawn ---
    try:
        from wiki import _client, FIELD_OK
        tmp = Path(tempfile.mkdtemp())
        try:
            wiki_path = tmp / "wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)
            (wiki_path / "tasks.json").write_text('{"_default": {}}', encoding="utf-8")

            state_file = wiki_path / ".wiki-daemon.json"
            state = {
                "protocol_version": PROTOCOL_VERSION,
                "pid": os.getpid() + 999999,
                "host": "127.0.0.1",
                "port": 9999,
                "token": "test-token",
            }
            state_file.write_text(json.dumps(state), encoding="utf-8")

            with patch("wiki._client.socket.create_connection") as mock_create_conn, \
                 patch("wiki._client._connect_send_recv") as mock_send_recv, \
                 patch("wiki._client._spawn_server") as mock_spawn:

                mock_create_conn.return_value = MagicMock(close=MagicMock())
                mock_send_recv.return_value = {FIELD_OK: True}

                result = _client._ensure_daemon(wiki_path)
                assert result == ("127.0.0.1", 9999, "test-token"), f"unexpected result: {result}"
                assert mock_spawn.call_count == 0, f"spawn_server should not be called, but was called {mock_spawn.call_count} times"
                ok("_ensure_daemon successful-health: returns tuple without respawn")
        finally:
            _safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)
    except Exception as exc:
        fail("_ensure_daemon successful-health: returns tuple without respawn", exc)

    # --- (k) OP_SET_DEPS round-trip via handle_request ---
    try:
        with safe_temp_dir() as tmp:
            wiki_path = tmp / "wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)
            (wiki_path / "tasks.json").write_text('{"_default": {}}', encoding="utf-8")

            wiki_server = WikiServer(wiki_path, idle_timeout=1)
            wiki_server._store.upsert_task({"slug": "task-a", "title": "Task A"})
            wiki_server._store.upsert_task({"slug": "task-b", "title": "Task B"})

            payload = {"slug": "task-b", "depends_on": ["task-a"]}
            resp = wiki_server.handle_request({FIELD_OP: OP_SET_DEPS, "payload": payload})

            assert resp.get(FIELD_OK) is True, f"response ok should be True, got {resp.get(FIELD_OK)}"
            task = wiki_server._store.get_task("task-b")
            assert task.get("depends_on") == ["task-a"], f"depends_on should be ['task-a'], got {task.get('depends_on')}"
            ok("OP_SET_DEPS round-trip via handle_request")
    except Exception as exc:
        fail("OP_SET_DEPS round-trip via handle_request", exc)

    # --- (l) OP_MIGRATE_DEPS round-trip ---
    try:
        from tinydb import TinyDB, Query
        with safe_temp_dir() as tmp:
            wiki_path = tmp / "wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)
            (wiki_path / "tasks.json").write_text('{"_default": {}}', encoding="utf-8")

            wiki_server = WikiServer(wiki_path, idle_timeout=1)

            # Insert a task with group="Z" by directly calling _db.insert
            # (bypassing upsert_task validation which rejects group keys)
            task_with_group = {
                "id": 0,
                "slug": "task-z",
                "title": "Task Z",
                "group": "Z",
                "depends_on": [],
                "isolated": False,
                "deferred": False,
                "brief": "",
                "body": "",
                "status": None,
            }
            wiki_server._store._db.insert(task_with_group)

            payload = {}
            resp = wiki_server.handle_request({FIELD_OP: OP_MIGRATE_DEPS, "payload": payload})

            assert resp.get(FIELD_OK) is True, f"response ok should be True, got {resp.get(FIELD_OK)}"
            task = wiki_server._store.get_task("task-z")
            assert task is not None, "task-z should exist"
            assert task.get("isolated") is True, f"isolated should be True, got {task.get('isolated')}"
            assert "group" not in task, f"group key should not exist, but found: {task.get('group')}"
            ok("OP_MIGRATE_DEPS round-trip")
    except Exception as exc:
        fail("OP_MIGRATE_DEPS round-trip", exc)

    # --- (m) list_tasks_brief enriched with layer ---
    try:
        with safe_temp_dir() as tmp:
            wiki_path = tmp / "wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)
            (wiki_path / "tasks.json").write_text('{"_default": {}}', encoding="utf-8")

            wiki_server = WikiServer(wiki_path, idle_timeout=1)
            wiki_server._store.upsert_task({"slug": "task-a", "title": "Task A"})
            wiki_server._store.upsert_task({"slug": "task-b", "title": "Task B", "depends_on": ["task-a"]})

            payload = {}
            resp = wiki_server.handle_request({FIELD_OP: OP_LIST_TASKS_BRIEF, "payload": payload})

            assert resp.get(FIELD_OK) is True, f"response ok should be True, got {resp.get(FIELD_OK)}"
            tasks = resp.get("tasks", [])
            assert len(tasks) == 2, f"expected 2 tasks, got {len(tasks)}"

            task_a = next((t for t in tasks if t["slug"] == "task-a"), None)
            task_b = next((t for t in tasks if t["slug"] == "task-b"), None)

            assert task_a is not None, "task-a should be in response"
            assert task_b is not None, "task-b should be in response"
            assert "layer" in task_a, "task-a should have layer key"
            assert "layer" in task_b, "task-b should have layer key"
            assert task_a["layer"] == "A", f"task-a layer should be 'A', got {task_a['layer']}"
            assert task_b["layer"] == "B", f"task-b layer should be 'B', got {task_b['layer']}"
            ok("list_tasks_brief enriched with layer")
    except Exception as exc:
        fail("list_tasks_brief enriched with layer", exc)

    # --- (n) Orphan cleanup regression ---
    try:
        import os as _os
        with safe_temp_dir() as tmp:
            wiki_path = tmp / "wiki"
            wiki_path.mkdir(parents=True, exist_ok=True)
            (wiki_path / "tasks.json").write_text('{"_default": {}}', encoding="utf-8")

            wiki_server = WikiServer(wiki_path, idle_timeout=1)

            # Insert task with body (proposal)
            wiki_server._store.upsert_task({"slug": "task-with-body", "title": "Task", "body": "proposal content"})

            # Call rerender with SKIP_PUSH=1 to commit but not push
            with patch.dict(_os.environ, {"WIKI_DAEMON_SKIP_PUSH": "1"}):
                wiki_server._render_and_commit_all(slug_for_msg="test")

            # Verify proposal file exists
            proposal_file = wiki_path / "proposal-task-with-body.md"
            assert proposal_file.exists(), "proposal file should exist after render"

            # Remove the task
            wiki_server._store.remove_task("task-with-body")

            # Rerender again
            with patch.dict(_os.environ, {"WIKI_DAEMON_SKIP_PUSH": "1"}):
                wiki_server._render_and_commit_all(slug_for_msg="test-remove")

            # Verify proposal file is deleted (orphan cleanup)
            assert not proposal_file.exists(), "proposal file should be deleted after task removal"
            ok("Orphan cleanup regression")
    except Exception as exc:
        fail("Orphan cleanup regression", exc)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
