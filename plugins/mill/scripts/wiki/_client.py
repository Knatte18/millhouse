"""Wiki client — public structured task API with transparent daemon auto-start."""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from wiki import (
    PROTOCOL_VERSION,
    OP_UPSERT_TASK,
    OP_UPSERT_TASKS_BATCH,
    OP_SET_PHASE,
    OP_REMOVE_TASK,
    OP_MERGE_TASKS,
    OP_GET_TASK,
    OP_LIST_TASKS_BRIEF,
    OP_LIST_TASKS_FULL,
    OP_HEALTH,
    OP_RERENDER,
    OP_SHUTDOWN,
    FIELD_OP,
    FIELD_TOKEN,
    FIELD_OK,
    FIELD_ERROR_TYPE,
    FIELD_ERROR,
    ERR_NOT_FOUND,
    ERR_PUSH_FAILED,
    WikiBusyError,
    WikiNotFoundError,
    WikiPushError,
    WikiProtocolError,
    WikiStartupError,
)

SPAWN_TIMEOUT: int = 20 if sys.platform == "win32" else 10
_SERVER_MODULE: str = "wiki._server"

# Registry of in-process WikiServer instances, keyed by resolved wiki_path.
# When a wiki_path is registered, all client ops route directly to the server's
# handle_request method instead of spawning a subprocess and talking over TCP.
# Intended for the unit test suite — production code never touches this map.
_INPROCESS_SERVERS: dict[str, "object"] = {}


def use_inprocess(wiki_path: Path) -> None:
    """Register an in-process WikiServer for ``wiki_path``, bypassing the daemon.

    After this call, every client op on this wiki_path is dispatched in the
    same Python process — no subprocess spawn, no socket, no token. Same
    semantics as the daemon path (writes tasks.json, renders files, commits
    via git; honours WIKI_DAEMON_SKIP_PUSH to skip the push step).

    Intended for unit tests. Production callers must not use this.

    Idempotent: calling twice on the same path is a no-op.
    """
    from wiki._server import WikiServer

    key = str(Path(wiki_path).resolve())
    if key in _INPROCESS_SERVERS:
        return
    server = WikiServer(Path(wiki_path))
    # Mirror the on_start side-effect (the only one is _ensure_gitignore).
    server._ensure_gitignore()
    _INPROCESS_SERVERS[key] = server


def stop_inprocess(wiki_path: Path) -> None:
    """Unregister the in-process server for ``wiki_path``.

    Safe to call when no server is registered. After this call, subsequent
    ops on this path fall back to the daemon TCP path.
    """
    key = str(Path(wiki_path).resolve())
    server = _INPROCESS_SERVERS.pop(key, None)
    if server is not None:
        try:
            server.on_stop()
        except Exception:
            pass


def _inprocess_server(wiki_path: Path):
    return _INPROCESS_SERVERS.get(str(Path(wiki_path).resolve()))


def wait_for_socket_reachable(host: str, port: int, *, timeout: float, interval: float = 0.1) -> bool:
    """Poll for socket reachability until timeout expires.

    Polls socket.create_connection every interval seconds until success or timeout.
    Does not raise on OSError or socket.timeout during polling.

    Args:
        host: Server host.
        port: Server port.
        timeout: Total timeout budget in seconds.
        interval: Poll interval in seconds (default 0.1).

    Returns:
        True if socket became reachable, False if timeout expired.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            per_attempt_timeout = min(0.5, max(0, deadline - time.monotonic()))
            sock = socket.create_connection((host, port), timeout=per_attempt_timeout)
            sock.close()
            return True
        except (OSError, socket.timeout):
            time.sleep(interval)
    return False


def _dispatch(wiki_path: Path, op: str, payload: dict) -> dict:
    """Route an op to either the in-process server or the daemon over TCP.

    When ``WIKI_DAEMON_INPROCESS=1`` is set in the environment, a transient
    in-process server is built per request and closed immediately afterwards.
    No file handles accumulate across requests, so tests using
    ``tempfile.TemporaryDirectory()`` can clean up reliably on Windows.
    Tests that explicitly call ``use_inprocess(path)`` keep a persistent
    server for that path (callers must call ``stop_inprocess(path)`` on
    teardown). The env-var auto-mode is the default for the unit suite.
    """
    server = _inprocess_server(wiki_path)
    if server is not None:
        return server.handle_request({FIELD_OP: op, "payload": payload})
    if os.environ.get("WIKI_DAEMON_INPROCESS") == "1":
        from wiki._server import WikiServer
        transient = WikiServer(Path(wiki_path))
        try:
            transient._ensure_gitignore()
            return transient.handle_request({FIELD_OP: op, "payload": payload})
        finally:
            try:
                transient.on_stop()
            except Exception:
                pass
    host, port, token = _ensure_daemon(wiki_path)
    req = {FIELD_OP: op, FIELD_TOKEN: token, "payload": payload}

    backoff_sleeps = [2, 4, 8]
    for attempt in range(4):
        try:
            return _connect_send_recv(host, port, req, timeout=3.0)
        except TimeoutError:
            if attempt < 3:
                time.sleep(backoff_sleeps[attempt])
            else:
                raise WikiBusyError(f"daemon stayed busy past retry budget for op: {op}")
    assert False, "unreachable: loop always exits via return or raise"


def upsert_task(
    wiki_path: Path,
    slug: str,
    *,
    title: str | None = None,
    brief: str | None = None,
    body: str | None = None,
    group: str | None = None,
    status: str | None = None,
) -> dict:
    """Upsert a task in the wiki.

    Args:
        wiki_path: Path to wiki clone root.
        slug: Task slug (required).
        title: Task title.
        brief: Task brief.
        body: Task body (proposal content).
        group: Task group.
        status: Task status.

    Returns:
        The upserted task dict.

    Raises:
        WikiPushError: Git push failed.
        WikiProtocolError: Protocol or message error.
        WikiStartupError: Daemon failed to start.
    """
    payload = {"slug": slug}
    if title is not None:
        payload["title"] = title
    if brief is not None:
        payload["brief"] = brief
    if body is not None:
        payload["body"] = body
    if group is not None:
        payload["group"] = group
    if status is not None:
        payload["status"] = status

    resp = _dispatch(wiki_path, OP_UPSERT_TASK, payload)

    if resp.get(FIELD_OK):
        return resp.get("task", {})

    error_type = resp.get(FIELD_ERROR_TYPE)
    if error_type == ERR_PUSH_FAILED:
        raise WikiPushError(resp.get(FIELD_ERROR, ""))

    raise WikiProtocolError(resp.get(FIELD_ERROR, ""))


def upsert_tasks_batch(
    wiki_path: Path,
    tasks: list[dict],
    *,
    message: str | None = None,
) -> None:
    """Upsert multiple tasks in a batch.

    Args:
        wiki_path: Path to wiki clone root.
        tasks: List of task dicts to upsert.
        message: Optional commit message tail.

    Raises:
        WikiPushError: Git push failed.
        WikiProtocolError: Protocol or message error.
        WikiStartupError: Daemon failed to start.
    """
    payload = {"tasks": tasks}
    if message is not None:
        payload["message"] = message

    resp = _dispatch(wiki_path, OP_UPSERT_TASKS_BATCH, payload)

    if resp.get(FIELD_OK):
        return

    error_type = resp.get(FIELD_ERROR_TYPE)
    if error_type == ERR_PUSH_FAILED:
        raise WikiPushError(resp.get(FIELD_ERROR, ""))

    raise WikiProtocolError(resp.get(FIELD_ERROR, ""))


def set_phase(
    wiki_path: Path,
    id_or_slug: int | str,
    phase: str | None,
) -> None:
    """Set or clear a task's phase/status.

    Args:
        wiki_path: Path to wiki clone root.
        id_or_slug: Task ID or slug.
        phase: Phase string or None to clear.

    Raises:
        WikiNotFoundError: Task not found.
        WikiPushError: Git push failed.
        WikiProtocolError: Protocol or message error.
        WikiStartupError: Daemon failed to start.
    """
    payload = {"id_or_slug": id_or_slug, "phase": phase}

    resp = _dispatch(wiki_path, OP_SET_PHASE, payload)

    if resp.get(FIELD_OK):
        return

    error_type = resp.get(FIELD_ERROR_TYPE)
    if error_type == ERR_NOT_FOUND:
        raise WikiNotFoundError(str(id_or_slug))
    if error_type == ERR_PUSH_FAILED:
        raise WikiPushError(resp.get(FIELD_ERROR, ""))

    raise WikiProtocolError(resp.get(FIELD_ERROR, ""))


def remove_task(
    wiki_path: Path,
    id_or_slug: int | str,
) -> None:
    """Remove a task from the wiki.

    Args:
        wiki_path: Path to wiki clone root.
        id_or_slug: Task ID or slug.

    Raises:
        WikiNotFoundError: Task not found.
        WikiPushError: Git push failed.
        WikiProtocolError: Protocol or message error.
        WikiStartupError: Daemon failed to start.
    """
    payload = {"id_or_slug": id_or_slug}

    resp = _dispatch(wiki_path, OP_REMOVE_TASK, payload)

    if resp.get(FIELD_OK):
        return

    error_type = resp.get(FIELD_ERROR_TYPE)
    if error_type == ERR_NOT_FOUND:
        raise WikiNotFoundError(str(id_or_slug))
    if error_type == ERR_PUSH_FAILED:
        raise WikiPushError(resp.get(FIELD_ERROR, ""))

    raise WikiProtocolError(resp.get(FIELD_ERROR, ""))


def get_task(
    wiki_path: Path,
    id_or_slug: int | str,
) -> dict | None:
    """Get a task by ID or slug.

    Args:
        wiki_path: Path to wiki clone root.
        id_or_slug: Task ID or slug.

    Returns:
        Task dict or None if not found.

    Raises:
        WikiProtocolError: Protocol or message error.
        WikiStartupError: Daemon failed to start.
    """
    payload = {"id_or_slug": id_or_slug}

    resp = _dispatch(wiki_path, OP_GET_TASK, payload)

    if resp.get(FIELD_OK):
        return resp.get("task")

    raise WikiProtocolError(resp.get(FIELD_ERROR, ""))


def list_tasks_brief(wiki_path: Path) -> list[dict]:
    """List all tasks with brief fields.

    Args:
        wiki_path: Path to wiki clone root.

    Returns:
        List of task dicts with keys {id, slug, title, group, brief, status, has_proposal}.

    Raises:
        WikiProtocolError: Protocol or message error.
        WikiStartupError: Daemon failed to start.
    """
    resp = _dispatch(wiki_path, OP_LIST_TASKS_BRIEF, {})

    if resp.get(FIELD_OK):
        return resp.get("tasks", [])

    raise WikiProtocolError(resp.get(FIELD_ERROR, ""))


def list_tasks_full(wiki_path: Path) -> list[dict]:
    """List all tasks with all fields.

    Args:
        wiki_path: Path to wiki clone root.

    Returns:
        List of task dicts with all TinyDB fields.

    Raises:
        WikiProtocolError: Protocol or message error.
        WikiStartupError: Daemon failed to start.
    """
    resp = _dispatch(wiki_path, OP_LIST_TASKS_FULL, {})

    if resp.get(FIELD_OK):
        return resp.get("tasks", [])

    raise WikiProtocolError(resp.get(FIELD_ERROR, ""))


def merge_tasks(
    wiki_path: Path,
    *,
    remove_slugs: list[str],
    upsert: dict,
    set_phase: tuple[str, str | None] | None = None,
) -> dict:
    """Perform atomic multi-step task operations: remove, upsert, set phase.

    Args:
        wiki_path: Path to wiki clone root.
        remove_slugs: Slugs to remove.
        upsert: Task dict to upsert.
        set_phase: Tuple of (slug_or_id, phase) to set, or None.

    Returns:
        The upserted task dict.

    Raises:
        WikiPushError: Git push failed.
        WikiProtocolError: Protocol or message error.
        WikiStartupError: Daemon failed to start.
    """
    payload = {
        "remove_slugs": remove_slugs,
        "upsert": upsert,
        "set_phase": set_phase,
    }

    resp = _dispatch(wiki_path, OP_MERGE_TASKS, payload)

    if resp.get(FIELD_OK):
        return resp.get("task", {})

    error_type = resp.get(FIELD_ERROR_TYPE)
    if error_type == ERR_PUSH_FAILED:
        raise WikiPushError(resp.get(FIELD_ERROR, ""))

    raise WikiProtocolError(resp.get(FIELD_ERROR, ""))


def rerender(wiki_path: Path) -> None:
    """Re-render derived files (Home.md, _Sidebar.md, proposal-*.md) from tasks.json.

    Commits and pushes only if output differs from on-disk content.

    Args:
        wiki_path: Path to wiki clone root.

    Raises:
        WikiPushError: Git push failed.
        WikiProtocolError: Protocol or message error.
        WikiStartupError: Daemon failed to start.
    """
    resp = _dispatch(wiki_path, OP_RERENDER, {})

    if resp.get(FIELD_OK):
        return

    error_type = resp.get(FIELD_ERROR_TYPE)
    if error_type == ERR_PUSH_FAILED:
        raise WikiPushError(resp.get(FIELD_ERROR, ""))

    raise WikiProtocolError(resp.get(FIELD_ERROR, ""))


def shutdown(wiki_path: Path) -> bool:
    """Request a clean daemon shutdown. Returns False if no daemon is running.

    The daemon will respawn automatically on the next request.

    Args:
        wiki_path: Path to wiki clone root.

    Returns:
        True if shutdown was requested, False if no daemon was running.
    """
    state_file = wiki_path / ".wiki-daemon.json"
    if not state_file.exists():
        return False

    try:
        state = json.loads(state_file.read_text("utf-8"))
        host = state.get("host", "127.0.0.1")
        port = state.get("port", 0)
        token = state.get("token", "")
    except Exception:
        return False

    if not all([host, port, token]):
        return False

    req = {FIELD_OP: OP_SHUTDOWN, FIELD_TOKEN: token, "payload": {}}
    try:
        _connect_send_recv(host, port, req)
    except OSError:
        return False
    return True


def health_check(wiki_path: Path) -> bool:
    """Ensure the daemon is up and responding, spawning it if needed.

    Semantically equivalent to every other client op: auto-spawns when the
    state file is missing, stale, or the daemon is dead. Returns False only
    when spawn itself fails (e.g. WikiStartupError) or the live daemon
    rejects the health probe.

    Args:
        wiki_path: Path to wiki clone root.

    Returns:
        True if the daemon is alive (possibly after a fresh spawn), False
        if it could not be brought up.
    """
    try:
        resp = _dispatch(wiki_path, OP_HEALTH, {})
        return bool(resp.get(FIELD_OK))
    except Exception:
        return False


def _ensure_daemon(wiki_path: Path) -> tuple[str, int, str]:
    """Ensure daemon is running and return (host, port, token).

    Checks state file, respawns if stale or version mismatch, waits for startup.

    Args:
        wiki_path: Path to wiki clone root.

    Returns:
        Tuple of (host, port, token).

    Raises:
        WikiStartupError: Daemon failed to start within timeout.
    """
    state_file = wiki_path / ".wiki-daemon.json"

    def _read_state_file() -> dict | None:
        """Read state file, bypassing Path.read_text() mocks in tests."""
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    if state_file.exists():
        state = _read_state_file()
        if state:
            if state.get("protocol_version") != PROTOCOL_VERSION:
                _kill_daemon(state)
                poll_deadline = time.monotonic() + 5.0
                while time.monotonic() < poll_deadline:
                    if not state_file.exists():
                        break
                    time.sleep(0.1)
                state_file.unlink(missing_ok=True)
            else:
                try:
                    sock = socket.create_connection(
                        (state["host"], state["port"]), timeout=0.5
                    )
                    sock.close()
                    req = {FIELD_OP: OP_HEALTH, FIELD_TOKEN: state["token"], "payload": {}}
                    try:
                        resp = _connect_send_recv(state["host"], state["port"], req, timeout=1.0)
                        if resp.get(FIELD_OK) is True:
                            return (state["host"], state["port"], state["token"])
                    except OSError:
                        pass
                    if _is_stale(state):
                        state_file.unlink(missing_ok=True)
                except OSError:
                    if _is_stale(state):
                        state_file.unlink(missing_ok=True)

    _spawn_server(wiki_path)

    deadline = time.monotonic() + SPAWN_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(0.1)
        state = _read_state_file()
        if state:
            if wait_for_socket_reachable(state["host"], state["port"], timeout=deadline - time.monotonic()):
                return (state["host"], state["port"], state["token"])

    raise WikiStartupError("daemon did not start within timeout")


def _spawn_server(wiki_path: Path) -> None:
    """Spawn wiki daemon in a detached process.

    Args:
        wiki_path: Path to wiki clone root.
    """
    cmd = [sys.executable, "-m", _SERVER_MODULE, str(wiki_path)]

    env = dict(os.environ)
    scripts_dir = str(Path(__file__).parent.parent)
    pythonpath = env.get("PYTHONPATH", "")
    if pythonpath:
        env["PYTHONPATH"] = (scripts_dir + os.pathsep + pythonpath).strip(os.pathsep)
    else:
        env["PYTHONPATH"] = scripts_dir

    if sys.platform == "win32":
        CREATE_NO_WINDOW = 0x08000000
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_BREAKAWAY_FROM_JOB = 0x01000000
        launch_cmd = ["cmd", "/c", "start", "", "/B", "/MIN"] + cmd
        subprocess.Popen(
            launch_cmd,
            env=env,
            close_fds=True,
            creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB,
        )
    else:
        subprocess.Popen(cmd, env=env, close_fds=True, start_new_session=True)


def _connect_send_recv(host: str, port: int, msg: dict, *, timeout: float = 10.0) -> dict:
    """Send JSON request and receive JSON response over TCP.

    Args:
        host: Server host.
        port: Server port.
        msg: Request dict to send.
        timeout: Connection timeout in seconds (default 10.0).

    Returns:
        Response dict.

    Raises:
        OSError: Connection or I/O error.
    """
    sock = socket.create_connection((host, port), timeout=timeout)
    try:
        sock.sendall(json.dumps(msg).encode("utf-8"))
        sock.shutdown(socket.SHUT_WR)

        chunks = bytearray()
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.extend(chunk)

        return json.loads(chunks.decode("utf-8"))
    finally:
        sock.close()


def _kill_daemon(state: dict) -> None:
    """Kill daemon process by PID.

    Args:
        state: State dict containing 'pid'.
    """
    pid = state.get("pid")
    if pid is None:
        return

    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)], capture_output=True
            )
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def _is_stale(state: dict) -> bool:
    """Check if daemon state is stale: dead PID or unreachable port.

    Args:
        state: State dict containing 'pid', 'host', 'port'.

    Returns:
        True if daemon is stale, False if alive.
    """
    pid = state.get("pid")
    if pid is None:
        return True

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    except Exception:
        return True

    host = state.get("host", "127.0.0.1")
    port = state.get("port", 0)
    if port == 0:
        return True

    try:
        sock = socket.create_connection((host, port), timeout=0.5)
        sock.close()
        return False
    except (socket.timeout, ConnectionRefusedError, OSError):
        return True
