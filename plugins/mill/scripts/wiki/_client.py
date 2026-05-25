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
    FIELD_OP,
    FIELD_TOKEN,
    FIELD_OK,
    FIELD_ERROR_TYPE,
    FIELD_ERROR,
    ERR_NOT_FOUND,
    ERR_PUSH_FAILED,
    WikiNotFoundError,
    WikiPushError,
    WikiProtocolError,
    WikiStartupError,
)

SPAWN_TIMEOUT: int = 10
_SERVER_MODULE: str = "wiki._server"


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

    host, port, token = _ensure_daemon(wiki_path)
    req = {FIELD_OP: OP_UPSERT_TASK, FIELD_TOKEN: token, "payload": payload}

    resp = _connect_send_recv(host, port, req)

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

    host, port, token = _ensure_daemon(wiki_path)
    req = {FIELD_OP: OP_UPSERT_TASKS_BATCH, FIELD_TOKEN: token, "payload": payload}

    resp = _connect_send_recv(host, port, req)

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

    host, port, token = _ensure_daemon(wiki_path)
    req = {FIELD_OP: OP_SET_PHASE, FIELD_TOKEN: token, "payload": payload}

    resp = _connect_send_recv(host, port, req)

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

    host, port, token = _ensure_daemon(wiki_path)
    req = {FIELD_OP: OP_REMOVE_TASK, FIELD_TOKEN: token, "payload": payload}

    resp = _connect_send_recv(host, port, req)

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

    host, port, token = _ensure_daemon(wiki_path)
    req = {FIELD_OP: OP_GET_TASK, FIELD_TOKEN: token, "payload": payload}

    resp = _connect_send_recv(host, port, req)

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
    payload = {}

    host, port, token = _ensure_daemon(wiki_path)
    req = {FIELD_OP: OP_LIST_TASKS_BRIEF, FIELD_TOKEN: token, "payload": payload}

    resp = _connect_send_recv(host, port, req)

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
    payload = {}

    host, port, token = _ensure_daemon(wiki_path)
    req = {FIELD_OP: OP_LIST_TASKS_FULL, FIELD_TOKEN: token, "payload": payload}

    resp = _connect_send_recv(host, port, req)

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

    host, port, token = _ensure_daemon(wiki_path)
    req = {FIELD_OP: OP_MERGE_TASKS, FIELD_TOKEN: token, "payload": payload}

    resp = _connect_send_recv(host, port, req)

    if resp.get(FIELD_OK):
        return resp.get("task", {})

    error_type = resp.get(FIELD_ERROR_TYPE)
    if error_type == ERR_PUSH_FAILED:
        raise WikiPushError(resp.get(FIELD_ERROR, ""))

    raise WikiProtocolError(resp.get(FIELD_ERROR, ""))


def health_check(wiki_path: Path) -> bool:
    """Check if daemon is alive and responding.

    Args:
        wiki_path: Path to wiki clone root.

    Returns:
        True if daemon is alive, False otherwise.
    """
    try:
        state_file = wiki_path / ".wiki-daemon.json"
        if not state_file.exists():
            return False

        state = json.loads(state_file.read_text("utf-8"))
        host = state.get("host", "127.0.0.1")
        port = state.get("port", 0)
        token = state.get("token", "")

        if not all([host, port, token]):
            return False

        req = {FIELD_OP: OP_HEALTH, FIELD_TOKEN: token, "payload": {}}
        _connect_send_recv(host, port, req)
        return True
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

    if state_file.exists():
        try:
            state = json.loads(state_file.read_text("utf-8"))

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
                    return (state["host"], state["port"], state["token"])
                except OSError:
                    if _is_stale(state):
                        state_file.unlink(missing_ok=True)
                    else:
                        return (state["host"], state["port"], state["token"])
        except Exception:
            pass

    _spawn_server(wiki_path)

    deadline = time.monotonic() + SPAWN_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(0.1)
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text("utf-8"))
                sock = socket.create_connection(
                    (state["host"], state["port"]), timeout=0.5
                )
                sock.close()
                return (state["host"], state["port"], state["token"])
            except Exception:
                pass

    raise WikiStartupError("daemon did not start within timeout")


def _spawn_server(wiki_path: Path) -> None:
    """Spawn wiki daemon in a detached process.

    When MILL_WIKI_DAEMON_DEBUG=1, child stdout+stderr are captured to <wiki_path>/.wiki-daemon-debug.log for diagnostic use. Default-off path unchanged.

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

    if os.environ.get("MILL_WIKI_DAEMON_DEBUG") == "1":
        debug_log = wiki_path / ".wiki-daemon-debug.log"
        wiki_path.mkdir(parents=True, exist_ok=True)
        log_file = open(debug_log, "w", encoding="utf-8")
        try:
            if sys.platform == "win32":
                CREATE_NO_WINDOW = 0x08000000
                CREATE_NEW_PROCESS_GROUP = 0x00000200
                CREATE_BREAKAWAY_FROM_JOB = 0x01000000
                subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    close_fds=True,
                    creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB,
                )
            else:
                subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    close_fds=True,
                    start_new_session=True,
                )
        finally:
            log_file.close()
        return

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


def _connect_send_recv(host: str, port: int, msg: dict) -> dict:
    """Send JSON request and receive JSON response over TCP.

    Args:
        host: Server host.
        port: Server port.
        msg: Request dict to send.

    Returns:
        Response dict.

    Raises:
        OSError: Connection or I/O error.
    """
    sock = socket.create_connection((host, port), timeout=10.0)
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
