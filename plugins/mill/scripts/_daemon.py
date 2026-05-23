"""Generic daemon base class — TCP accept loop, JSON framing, token auth, state-file management."""
import abc
import datetime
import json
import logging
import os
import socket
import time
from pathlib import Path
from secrets import token_hex


class DaemonBase(abc.ABC):
    """Generic daemon base — subclass provides handle_request, identity, and lifecycle callbacks."""

    _protocol_version: int = 0

    def __init__(self, name: str, state_file_path: Path, idle_timeout: int) -> None:
        """Initialize daemon with identity and config.

        Args:
            name: Daemon name for logging.
            state_file_path: Path to state file (PID, port, token, etc).
            idle_timeout: Seconds before idle-exit.
        """
        self._name = name
        self._state_file_path = Path(state_file_path)
        self._idle_timeout = idle_timeout
        self._logger = logging.getLogger(self._name)
        self._token: str | None = None

    @abc.abstractmethod
    def handle_request(self, msg: dict) -> dict:
        """Handle authenticated request. Subclass must override.

        Args:
            msg: Parsed JSON request dict.

        Returns:
            Response dict (will be JSON-encoded and sent).
        """
        ...

    def on_start(self, port: int, token: str) -> None:
        """Lifecycle hook: called after bind/token-gen, before accept loop. Default no-op.

        Args:
            port: Bound TCP port.
            token: Generated token for this daemon instance.
        """
        pass

    def on_stop(self) -> None:
        """Lifecycle hook: called on idle-exit before state-file removal. Default no-op."""
        pass

    def run(self) -> None:
        """Main entry point: O_EXCL claim, bind, accept loop, idle-exit."""
        if not logging.root.handlers:
            logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")

        claimed = False
        try:
            if not self._claim_state_file():
                return
            claimed = True

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.listen(64)
            sock.settimeout(1.0)

            token = token_hex(16)
            self._token = token

            state = {
                "protocol_version": self._protocol_version,
                "pid": os.getpid(),
                "host": "127.0.0.1",
                "port": port,
                "token": token,
                "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            self._write_state_file(self._state_file_path, state)

            self.on_start(port, token)

            last_activity = time.monotonic()
            while True:
                try:
                    conn, _ = sock.accept()
                    last_activity = time.monotonic()
                    self._handle_connection(conn)
                except socket.timeout:
                    if time.monotonic() - last_activity > self._idle_timeout:
                        self._logger.info("idle-exit")
                        break
        finally:
            if claimed:
                self.on_stop()
                self._state_file_path.unlink(missing_ok=True)

    def _claim_state_file(self) -> bool:
        """Claim state file with O_EXCL; on conflict check staleness.

        Returns:
            True if successfully claimed, False if another daemon is running.
        """
        while True:
            try:
                open(self._state_file_path, "x").close()
                return True
            except FileExistsError:
                state_text = self._state_file_path.read_text(encoding="utf-8")
                state = json.loads(state_text)
                if self._is_stale(state):
                    self._state_file_path.unlink()
                else:
                    self._logger.info("another daemon is running, exiting")
                    return False

    def _handle_connection(self, conn: socket.socket) -> None:
        """Handle one connection: read JSON, auth, dispatch, respond."""
        try:
            chunks = []
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)

            msg_text = b"".join(chunks).decode("utf-8")
            msg = json.loads(msg_text)

            if msg.get("token") != self._token:
                resp = {
                    "ok": False,
                    "error_type": "auth_error",
                    "error": "bad token",
                }
                conn.sendall(json.dumps(resp).encode("utf-8"))
                return

            resp = self.handle_request(msg)
            conn.sendall(json.dumps(resp).encode("utf-8"))

        except Exception as exc:
            try:
                resp = {
                    "ok": False,
                    "error_type": "server_error",
                    "error": str(exc),
                }
                conn.sendall(json.dumps(resp).encode("utf-8"))
            except Exception:
                pass
            self._logger.error(f"exception in _handle_connection: {exc!r}")
        finally:
            conn.close()

    def _is_stale(self, state: dict) -> bool:
        """Check if daemon state is stale: dead PID or unreachable port."""
        pid = state.get("pid")
        if pid is None:
            return True

        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass
        except Exception:
            return True

        host = state.get("host", "127.0.0.1")
        port = state.get("port", 0)
        if port == 0:
            return True

        try:
            test_sock = socket.create_connection((host, port), timeout=0.5)
            test_sock.close()
            return False
        except (socket.timeout, ConnectionRefusedError, OSError):
            return True

    def _write_state_file(self, path: Path, data: dict) -> None:
        """Write state file atomically: temp+rename."""
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp_path, path)
