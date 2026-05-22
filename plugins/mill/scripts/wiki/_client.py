"""Wiki client — public read/write API with transparent daemon auto-start."""
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
    OP_READ,
    OP_WRITE,
    FIELD_OP,
    FIELD_TOKEN,
    FIELD_PATH,
    FIELD_OK,
    FIELD_CONTENT,
    FIELD_HASH,
    FIELD_ERROR_TYPE,
    FIELD_ERROR,
    FIELD_FILES,
    FIELD_MESSAGE,
    FIELD_BASE_HASH,
    FIELD_NEW_CONTENT,
    ERR_NOT_FOUND,
    ERR_CONFLICT,
    ERR_PUSH_FAILED,
    WikiNotFoundError,
    WikiConflictError,
    WikiPushError,
    WikiProtocolError,
    WikiStartupError,
)

SPAWN_TIMEOUT: int = 10
CAS_RETRIES: int = 3  # Exported for callers; not used internally in _client.py
_SERVER_MODULE: str = "wiki._server"


def read(
    wiki_path: Path,
    rel_path: str,
    *,
    refresh_interval: float = 10.0,
    idle_timeout: int = 600,
) -> tuple[str, str]:
    """Read a file from the wiki with automatic daemon management.

    Args:
        wiki_path: Path to wiki clone root.
        rel_path: Relative path within wiki.
        refresh_interval: Seconds between lazy pulls.
        idle_timeout: Seconds before idle-exit.

    Returns:
        Tuple of (content, hash).

    Raises:
        WikiNotFoundError: File not found.
        WikiProtocolError: Protocol or message error.
        WikiStartupError: Daemon failed to start.
    """
    host, port, token = _ensure_daemon(
        wiki_path, idle_timeout=idle_timeout, refresh_interval=refresh_interval
    )

    req = {FIELD_OP: OP_READ, FIELD_TOKEN: token, FIELD_PATH: rel_path}

    try:
        resp = _connect_send_recv(host, port, token, req)
    except OSError:
        host, port, token = _ensure_daemon(
            wiki_path, idle_timeout=idle_timeout, refresh_interval=refresh_interval
        )
        try:
            resp = _connect_send_recv(host, port, token, req)
        except OSError as e:
            raise WikiStartupError("daemon connection failed after retry") from e

    if resp.get(FIELD_OK):
        return (resp.get(FIELD_CONTENT, ""), resp.get(FIELD_HASH, ""))

    error_type = resp.get(FIELD_ERROR_TYPE)
    if error_type == ERR_NOT_FOUND:
        raise WikiNotFoundError(rel_path)

    raise WikiProtocolError(resp.get(FIELD_ERROR, ""))


def write_commit_push(
    wiki_path: Path,
    files: dict[str, tuple[str, str]],
    message: str,
    *,
    refresh_interval: float = 10.0,
    idle_timeout: int = 600,
) -> None:
    """Write files to the wiki with CAS and automatic daemon management.

    Args:
        wiki_path: Path to wiki clone root.
        files: Mapping of rel_path -> (new_content, base_hash).
        message: Commit message.
        refresh_interval: Seconds between lazy pulls.
        idle_timeout: Seconds before idle-exit.

    Raises:
        WikiConflictError: CAS conflict detected.
        WikiPushError: Git push failed.
        WikiProtocolError: Protocol or message error.
        WikiStartupError: Daemon failed to start.
    """
    host, port, token = _ensure_daemon(
        wiki_path, idle_timeout=idle_timeout, refresh_interval=refresh_interval
    )

    files_payload = {
        k: {FIELD_NEW_CONTENT: v[0], FIELD_BASE_HASH: v[1]} for k, v in files.items()
    }
    req = {
        FIELD_OP: OP_WRITE,
        FIELD_TOKEN: token,
        FIELD_FILES: files_payload,
        FIELD_MESSAGE: message,
    }

    try:
        resp = _connect_send_recv(host, port, token, req)
    except OSError as e:
        raise WikiStartupError("daemon connection failed") from e

    if resp.get(FIELD_OK):
        return

    error_type = resp.get(FIELD_ERROR_TYPE)
    if error_type == ERR_CONFLICT:
        raise WikiConflictError(resp.get(FIELD_ERROR, ""))
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

        req = {FIELD_OP: OP_READ, FIELD_TOKEN: token, FIELD_PATH: ""}
        _connect_send_recv(host, port, token, req)
        return True
    except Exception:
        return False


def _ensure_daemon(
    wiki_path: Path, *, idle_timeout: int, refresh_interval: float
) -> tuple[str, int, str]:
    """Ensure daemon is running and return (host, port, token).

    Checks state file, respawns if stale or version mismatch, waits for startup.

    Args:
        wiki_path: Path to wiki clone root.
        idle_timeout: Seconds before idle-exit.
        refresh_interval: Seconds between lazy pulls.

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

    _spawn_server(wiki_path, idle_timeout, refresh_interval)

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


def _spawn_server(
    wiki_path: Path, idle_timeout: int, refresh_interval: float
) -> None:
    """Spawn wiki daemon in a detached process.

    Args:
        wiki_path: Path to wiki clone root.
        idle_timeout: Seconds before idle-exit.
        refresh_interval: Seconds between lazy pulls.
    """
    cmd = [sys.executable, "-m", _SERVER_MODULE, str(wiki_path), str(idle_timeout), str(refresh_interval)]

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


def _connect_send_recv(host: str, port: int, token: str, msg: dict) -> dict:
    """Send JSON request and receive JSON response over TCP.

    Args:
        host: Server host.
        port: Server port.
        token: Authentication token (unused here, but part of msg).
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
