# Batch: Wiki server

```yaml
task: V3 wiki module with daemon and in-process cache
batch: Wiki server
number: 4
cards: 1
verify: null
depends-on: [1, 2, 3]
```

## Batch Scope

Creates `wiki/_server.py` — the wiki-specific daemon server. Subclasses `DaemonBase` from `_daemon.py`, instantiates a `Store` from `wiki/_store.py`, and uses `wiki/_sync.py` for all git operations. Implements `handle_request` to dispatch `read` and `write_commit_push` protocol operations. Owns the lazy-refresh interval, CAS base-hash checking, `.gitignore` housekeeping, and the `logging.handlers.RotatingFileHandler` log setup. Also provides the `__main__` entry point `_client.py` will invoke to spawn the server process.

## Cards

### Card 5: `wiki/_server.py` — wiki daemon server

- **Context:**
  - `plugins/mill/scripts/_daemon.py`
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_store.py`
  - `plugins/mill/scripts/wiki/_sync.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/wiki/_server.py`
- **Deletes:** none
- **Requirements:**
  Stdlib imports: `logging`, `logging.handlers`, `os`, `pathlib`, `sys`, `time`. From `_daemon` import `DaemonBase`. From `wiki` import protocol constants and exceptions. From `wiki._store` import `Store`. From `wiki._sync` import `path_guard`, `pull`, `atomic_write`, `commit_push`. No other imports outside stdlib and this package.

  **`class WikiServer(DaemonBase)`:**

  `_protocol_version = 1`

  `__init__(self, wiki_path: Path, *, idle_timeout: int = 600, refresh_interval: float = 10.0)`:
  - `super().__init__("wiki", wiki_path / ".wiki-daemon.json", idle_timeout)`
  - `self._wiki_path = wiki_path`
  - `self._refresh_interval = refresh_interval`
  - `self._store = Store()`
  - `self._last_pull: float = 0.0`
  - Set up `logging` with `RotatingFileHandler(wiki_path / ".wiki-daemon.log", maxBytes=1_000_000, backupCount=2)`, mode `'w'` on the handler to truncate on startup. Format: ASCII-only `"%(asctime)s %(levelname)s %(message)s"`. Store as `self._log = logging.getLogger("wiki-server")`.

  `on_start(self, port: int, token: str) -> None`:
  - Log (ASCII-only): `"wiki-server started pid=%d port=%d" % (os.getpid(), port)`.
  - Call `self._ensure_gitignore()`.

  `on_stop(self) -> None`:
  - Log "wiki-server stopping".

  `handle_request(self, msg: dict) -> dict`:
  - Dispatch on `msg.get(FIELD_OP)`: `OP_READ` → `_handle_read(msg)`, `OP_WRITE` → `_handle_write(msg)`, else `{FIELD_OK: False, FIELD_ERROR_TYPE: ERR_PROTOCOL, FIELD_ERROR: "unknown op"}`.

  `_handle_read(self, msg: dict) -> dict`:
  - `rel_path = msg.get(FIELD_PATH, "")`. Call `path_guard(rel_path)` — on `WikiPathError` return `{FIELD_OK: False, FIELD_ERROR_TYPE: ERR_PATH, FIELD_ERROR: str(e)}`.
  - Lazy refresh: if `time.monotonic() - self._last_pull > self._refresh_interval`: set `self._last_pull = time.monotonic()` first (before calling `pull()`), then call `pull(self._wiki_path)`, `self._store.invalidate_all()`. Setting `_last_pull` before the call ensures the refresh interval is honored even if `pull()` raises — preventing a request-rate hammer on a transiently unavailable remote.
  - Try cache: `hit = self._store.get(rel_path)`. If hit: return `{FIELD_OK: True, FIELD_CONTENT: hit[0], FIELD_HASH: hit[1]}`.
  - Miss: read from disk `(self._wiki_path / rel_path).read_text("utf-8")`. If `FileNotFoundError`: return `{FIELD_OK: False, FIELD_ERROR_TYPE: ERR_NOT_FOUND, FIELD_ERROR: rel_path}`. Store in cache via `self._store.set(rel_path, content)`. Re-read hash from store: `_, hash_ = self._store.get(rel_path)`. Return `{FIELD_OK: True, FIELD_CONTENT: content, FIELD_HASH: hash_}`.

  `_handle_write(self, msg: dict) -> dict`:
  - `files_payload = msg.get(FIELD_FILES, {})` — format `{rel_path: {FIELD_NEW_CONTENT: str, FIELD_BASE_HASH: str}}`. `message = msg.get(FIELD_MESSAGE, "wiki: update")`.
  - Pull before write (always): `pull(self._wiki_path)`, `self._store.invalidate_all()`, `self._last_pull = time.monotonic()`.
  - CAS check: for each `(rel_path, entry)` in `files_payload`: `path_guard(rel_path)`. Current hash = `self._store.get(rel_path)[1]` if in cache, else compute from disk (`Store.content_hash(disk_content)`) or treat as `""` if file absent. If `entry[FIELD_BASE_HASH] != current_hash`: return `{FIELD_OK: False, FIELD_ERROR_TYPE: ERR_CONFLICT, FIELD_ERROR: f"conflict on {rel_path}"}`.
  - Write phase: for each file: `atomic_write(self._wiki_path, rel_path, entry[FIELD_NEW_CONTENT])`.
  - `commit_push(self._wiki_path, list(files_payload.keys()), message)` — on `WikiPushError`: return `{FIELD_OK: False, FIELD_ERROR_TYPE: ERR_PUSH_FAILED, FIELD_ERROR: str(e)}`.
  - Invalidate written paths in cache. Return `{FIELD_OK: True}`.

  `_ensure_gitignore(self) -> None`:
  - Read `self._wiki_path / ".gitignore"` (empty string if absent). Check if `.wiki-daemon.json` and `.wiki-daemon.log` are present as lines. If both present: return (idempotent).
  - Append missing entries. Write file. Try `commit_push(self._wiki_path, [".gitignore"], "chore(wiki): gitignore daemon artifacts")`. On any exception: log warning (ASCII), continue — startup not aborted over gitignore hygiene.

  **`__main__` entry point** at module bottom:
  ```python
  if __name__ == "__main__":
      import sys
      wiki_path = Path(sys.argv[1])
      idle_timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 600
      refresh_interval = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
      WikiServer(wiki_path, idle_timeout=idle_timeout, refresh_interval=refresh_interval).run()
  ```

- **Commit:** `feat(wiki): add _server.py wiki daemon server`

## Batch Tests

`verify: null` — no runnable standalone test at this stage. The implementer verifies with an import check: `PYTHONPATH=plugins/mill/scripts python -c "from wiki._server import WikiServer; print('ok')"`. End-to-end behavior tested in Batch 7 integration test.
