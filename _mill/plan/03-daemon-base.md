# Batch: Generic daemon base

```yaml
task: V3 wiki module with daemon and in-process cache
batch: Generic daemon base
number: 3
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Creates `plugins/mill/scripts/_daemon.py` — a generic, mill-agnostic daemon base class. Zero dependencies on any mill helper or wiki subpackage (stdlib only). It owns the TCP accept loop, JSON framing, token auth, state-file management, O_EXCL spawn-race claim, PID-liveness stale detection, and idle-exit logic. The wiki server (Batch 4) subclasses it and supplies only the four seams: `handle_request`, daemon identity (name + state-file path), `idle_timeout`, and `on_start`/`on_stop` lifecycle callbacks. This batch is a root node — it can run in parallel with Batch 1.

Batch-local decision: `_daemon.py` is flat in `scripts/` (not inside `wiki/`) so future V3 modules can reuse it without importing from the wiki subpackage.

## Cards

### Card 4: `_daemon.py` — generic daemon base

- **Context:**
  - `plugins/mill/scripts/_bg.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_daemon.py`
- **Deletes:** none
- **Requirements:**
  Stdlib imports only: `abc`, `datetime`, `json`, `logging`, `os`, `pathlib`, `secrets`, `signal`, `socket`, `time`, `tempfile`. No mill imports.

  **`class DaemonBase(abc.ABC)`:**

  Constructor `__init__(self, name: str, state_file_path: Path, idle_timeout: int)` — stores params; `self._name`, `self._state_file_path`, `self._idle_timeout`.

  `@abc.abstractmethod handle_request(self, msg: dict) -> dict` — subclass must override; called per accepted connection after auth and JSON parse.

  `on_start(self, port: int, token: str) -> None` — lifecycle hook, default no-op.

  `on_stop(self) -> None` — lifecycle hook, default no-op.

  `run(self) -> None` — the main entry point:
  1. **O_EXCL claim**: call `self._claim_state_file()` which: tries `open(state_file, 'x').close()` — raises `FileExistsError` if already exists. On `FileExistsError`: try to read existing state; check `_is_stale(state)`. If stale: delete state file + retry `open(state_file, 'x').close()`. If not stale: log "another daemon is running, exiting" and return.
  2. Bind TCP socket: `sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)`, `sock.bind(('127.0.0.1', 0))`, `port = sock.getsockname()[1]`, `sock.listen(64)`, `sock.settimeout(1.0)`.
  3. Generate token: `token = secrets.token_hex(16)`.
  4. Write full state file atomically (temp+rename): `{"protocol_version": <subclass-provided int>, "pid": os.getpid(), "host": "127.0.0.1", "port": port, "token": token, "started_at": <ISO-8601 UTC>}`. The `protocol_version` comes from `self._protocol_version` (class-level attribute set by subclass).
  5. Call `self.on_start(port, token)`.
  6. **Accept loop**: `last_activity = time.monotonic()`. Loop: try `conn, _ = sock.accept()` with `sock.settimeout(1.0)` (already set). On `socket.timeout`: check idle-exit: if `time.monotonic() - last_activity > self._idle_timeout`: break. Continue. On successful accept: `self._handle_connection(conn)`. `last_activity = time.monotonic()`.
  7. On loop exit (idle-exit): call `self.on_stop()`. Remove state file (`state_file.unlink(missing_ok=True)`). Log "idle-exit".
  8. Wrap `run()` body in try/finally: cleanup (state file removal, `on_stop`) in finally so crashes don't leave stale state.

  `_handle_connection(self, conn: socket.socket) -> None` — wraps the per-request logic. In try/finally, close `conn`. Read until EOF: accumulate chunks. Decode UTF-8. Parse JSON. Check `msg.get("token") == self._token` (store token as instance var set during `run()`); on mismatch: send `{"ok": false, "error_type": "auth_error", "error": "bad token"}` and return. Call `self.handle_request(msg)`. Send response JSON encoded UTF-8. All exceptions caught: send error response; log ASCII-only error.

  `_is_stale(self, state: dict) -> bool` — parse `pid = state.get("pid")`. Try `os.kill(pid, 0)`: if `ProcessLookupError` → stale. If `PermissionError` → not stale (process exists, we lack permission). On any other error → assume stale. Also check connection: try `socket.create_connection((state.get("host", "127.0.0.1"), state.get("port", 0)), timeout=0.5)` — if connection refused → stale. Return False if PID alive and port accepting. Follow the same double-check pattern as `_bg.py`.

  `_write_state_file(self, path: Path, data: dict) -> None` — write to `path.with_suffix('.tmp')`, then `os.replace(tmp, path)`. Data serialized with `json.dumps(data, indent=2)`, encoded UTF-8.

  Class-level attribute `_protocol_version: int = 0` — subclass overrides: `_protocol_version = 1` (set in `WikiServer`). The base writes this into the state file.

- **Commit:** `feat(scripts): add _daemon.py generic daemon base`

## Batch Tests

`verify: null` — tested in Batch 6 (`test-wiki-daemon.py`). Import check: `PYTHONPATH=plugins/mill/scripts python -c "import _daemon; print('ok')"`.
