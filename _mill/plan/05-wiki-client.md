# Batch: Wiki client

```yaml
task: V3 wiki module with daemon and in-process cache
batch: Wiki client
number: 5
cards: 1
verify: null
depends-on: [4]
```

## Batch Scope

Creates `wiki/_client.py` — the public API callers use. Exposes `read()`, `write_commit_push()`, and `health_check()`. Implements transparent daemon auto-ensure: every call first checks whether the daemon is alive (reads the state file, tries a test connection) and spawns it if not. Implements `_spawn_server()` as an isolated, stdlib-only detached-Popen function that survives the parent Claude Code session exiting. Implements CAS retry (up to 3 attempts on `CONFLICT`) and `protocol_version` mismatch handling (kill stale daemon, respawn). The public API is the stable external surface; all other files in the package are internal.

Batch-local decision: `_spawn_server()` is the single implementation-specific seam (LSP model). Its internals are Windows-specific today (`DETACHED_PROCESS | CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP`); swapping the server later changes only this function.

## Cards

### Card 6: `wiki/_client.py` — client API with transparent daemon start

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_server.py`
  - `plugins/mill/scripts/_bg.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Deletes:** none
- **Requirements:**
  Stdlib imports only: `json`, `os`, `pathlib`, `signal`, `socket`, `subprocess`, `sys`, `time`. From `wiki` import all protocol constants and all exception classes. No other imports.

  **`SPAWN_TIMEOUT: int = 10`** — seconds to wait for daemon to come up.
  **`CAS_RETRIES: int = 3`** — max write retries on CONFLICT.
  **`_SERVER_MODULE: str = "wiki._server"`** — the `-m` argument for spawning.

  **`read(wiki_path: Path, rel_path: str, *, refresh_interval: float = 10.0, idle_timeout: int = 600) -> tuple[str, str]`**:
  - `host, port, token = _ensure_daemon(wiki_path, idle_timeout=idle_timeout, refresh_interval=refresh_interval)`.
  - Build request: `{"op": OP_READ, "token": token, "path": rel_path}`.
  - `resp = _connect_send_recv(host, port, token, req)` — on `OSError` (mid-request failure): one re-ensure + retry; on second failure raise `WikiStartupError`.
  - If `resp["ok"]`: return `(resp[FIELD_CONTENT], resp[FIELD_HASH])`. If `resp[FIELD_ERROR_TYPE] == ERR_NOT_FOUND`: raise `WikiNotFoundError(rel_path)`. Else raise `WikiProtocolError(resp.get(FIELD_ERROR, ""))`.

  **`write_commit_push(wiki_path: Path, files: dict[str, tuple[str, str]], message: str, *, refresh_interval: float = 10.0, idle_timeout: int = 600) -> None`**:
  - `files` maps `rel_path -> (new_content, base_hash)`.
  - `host, port, token = _ensure_daemon(wiki_path, idle_timeout=idle_timeout, refresh_interval=refresh_interval)`.
  - CAS retry loop (up to `CAS_RETRIES`): build request `{"op": OP_WRITE, "token": token, "files": {k: {"new_content": v[0], "base_hash": v[1]} for k, v in files.items()}, "message": message}`. Send. If `resp["ok"]`: return. If `ERR_CONFLICT`: re-read each conflicting file to get fresh `(content, hash)` via `_connect_send_recv` read request; update `files` dict with fresh base_hash and new_content recomputed by caller — wait, the caller supplies new_content; on CONFLICT the caller should recompute its edit on top of the fresh content. But since `_client.py` is a thin API (it doesn't know the caller's edit logic), on CONFLICT it raises `WikiConflictError` with the conflicting path — the caller re-reads and re-calls. Drop the inline retry loop in the client; raise immediately on CONFLICT; the integration test and callers retry at their level. This is simpler and correct: the client is not the right place for edit-recompute logic. Raise `WikiConflictError(path)` on first CONFLICT. If `ERR_PUSH_FAILED`: raise `WikiPushError`. Else raise `WikiProtocolError`.

  **`health_check(wiki_path: Path) -> bool`**:
  - Try to read state file. Try connect. Return True if daemon responds to a read request for a non-existent path (any response means alive). Return False on any exception.

  **`_ensure_daemon(wiki_path: Path, *, idle_timeout: int, refresh_interval: float) -> tuple[str, int, str]`**:
  - State file: `state_file = wiki_path / ".wiki-daemon.json"`.
  - If state file exists: parse JSON. Check `protocol_version`: if `state["protocol_version"] != PROTOCOL_VERSION`: kill old daemon (`_kill_daemon(state)`), wait for state file to disappear (poll `state_file.exists()` up to 5s, sleep 0.1s between polls); fall through to spawn.
  - Else (state file exists, version OK): try `socket.create_connection((state["host"], state["port"]), timeout=0.5).close()`. If succeeds: return `(state["host"], state["port"], state["token"])`.
  - On `OSError` (connection refused / stale): check `_is_stale(state)`. If stale: `state_file.unlink(missing_ok=True)`. Fall through to spawn.
  - Spawn: `_spawn_server(wiki_path, idle_timeout, refresh_interval)`. Poll: loop until `time.monotonic() < deadline` (deadline = now + SPAWN_TIMEOUT): sleep 0.1s; if state file exists and can connect: read state, return `(host, port, token)`. On timeout: raise `WikiStartupError("daemon did not start within timeout")`.

  **`_spawn_server(wiki_path: Path, idle_timeout: int, refresh_interval: float) -> None`**:
  - `cmd = [sys.executable, "-m", _SERVER_MODULE, str(wiki_path), str(idle_timeout), str(refresh_interval)]`.
  - `env = dict(os.environ)`. Ensure `PYTHONPATH` includes the `scripts/` directory (parent of `wiki/`): `scripts_dir = str(Path(__file__).parent.parent)`. Set `env["PYTHONPATH"] = scripts_dir` (preserve existing if present: `os.pathsep.join([scripts_dir, env.get("PYTHONPATH", "")])` stripped of trailing sep).
  - Windows branch (`sys.platform == "win32"`): `DETACHED_PROCESS = 0x00000008`, `CREATE_NO_WINDOW = 0x08000000`, `CREATE_NEW_PROCESS_GROUP = 0x00000200`. `subprocess.Popen(cmd, env=env, close_fds=True, creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP)`.
  - POSIX branch: `subprocess.Popen(cmd, env=env, close_fds=True, start_new_session=True)`.
  - Do not wait for the process; do not store the Popen object.

  **`_connect_send_recv(host: str, port: int, token: str, msg: dict) -> dict`**:
  - Open fresh TCP connection: `sock = socket.create_connection((host, port), timeout=10.0)`.
  - Send `json.dumps(msg).encode("utf-8")` then `sock.shutdown(socket.SHUT_WR)` to signal EOF.
  - Read until EOF: accumulate chunks into `bytearray`. Parse JSON. Close socket in finally.
  - Return parsed dict.

  **`_kill_daemon(state: dict) -> None`**:
  - `pid = state.get("pid")`. On Windows: `subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)`. On POSIX: `os.kill(pid, signal.SIGTERM)`. Ignore all exceptions.

  **`_is_stale(state: dict) -> bool`**:
  - Same pattern as `DaemonBase._is_stale`: try `os.kill(pid, 0)`: `ProcessLookupError` → True. `PermissionError` → False (alive). Then try connect: connection refused → True. Else False.

- **Commit:** `feat(wiki): add _client.py public API with transparent daemon start`

## Batch Tests

`verify: null` — the client requires a live daemon, so it is tested only in the integration test (Batch 7). Import check: `PYTHONPATH=plugins/mill/scripts python -c "from wiki import _client; print('ok')"`.
