# Batch: Wiki subpackage foundation

```yaml
task: V3 wiki module with daemon and in-process cache
batch: Wiki subpackage foundation
number: 1
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Creates the `wiki/` Python subpackage at `plugins/mill/scripts/wiki/`. This batch delivers two files: `__init__.py` (the shared protocol constants and exception hierarchy that every other module in the package imports) and `_store.py` (the in-process content cache). Both are pure Python with zero network or subprocess logic. They are the stable foundation the rest of the package builds on — subsequent batches can import from `wiki` immediately.

Batch-local decision: `_store.py` exposes a stateful `Store` class rather than module-level functions so tests and the server can create independent instances.

## Cards

### Card 1: `wiki/__init__.py` — protocol constants and exceptions

- **Context:** none
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Deletes:** none
- **Requirements:**
  Define `PROTOCOL_VERSION: int = 1`. Define the exception hierarchy (all inherit from `WikiError(Exception)`): `WikiNotFoundError`, `WikiConflictError`, `WikiPushError`, `WikiProtocolError`, `WikiStartupError`, `WikiPathError`. Define protocol string constants as module-level variables: `OP_READ = "read"`, `OP_WRITE = "write_commit_push"`, `FIELD_OK = "ok"`, `FIELD_CONTENT = "content"`, `FIELD_HASH = "hash"`, `FIELD_ERROR_TYPE = "error_type"`, `FIELD_ERROR = "error"`, `FIELD_OP = "op"`, `FIELD_TOKEN = "token"`, `FIELD_PATH = "path"`, `FIELD_FILES = "files"`, `FIELD_MESSAGE = "message"`, `FIELD_BASE_HASH = "base_hash"`, `FIELD_NEW_CONTENT = "new_content"`, `ERR_NOT_FOUND = "not_found"`, `ERR_CONFLICT = "conflict"`, `ERR_PUSH_FAILED = "push_failed"`, `ERR_PROTOCOL = "protocol_error"`, `ERR_AUTH = "auth_error"`, `ERR_PATH = "path_error"`. No imports outside stdlib (no imports at all in this file beyond `from __future__ import annotations`).
- **Commit:** `feat(wiki): add wiki subpackage __init__ with PROTOCOL_VERSION and exceptions`

### Card 2: `wiki/_store.py` — in-process content cache

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/wiki/_store.py`
- **Deletes:** none
- **Requirements:**
  Import `hashlib` from stdlib only. Define `class Store`: instance var `_cache: dict[str, tuple[str, str]]` (maps `rel_path -> (content, hash)`). `@staticmethod content_hash(content: str) -> str` — returns `hashlib.sha256(content.encode("utf-8")).hexdigest()`; decorated `@staticmethod` so callers can invoke it as `Store.content_hash(content)` without an instance. Method `set(rel_path: str, content: str) -> None` — computes hash via `Store.content_hash(content)`, stores `(content, hash)`. Method `get(rel_path: str) -> tuple[str, str] | None` — returns `(content, hash)` or `None` on miss. Method `invalidate(rel_path: str) -> None` — removes the entry (no-op if absent). Method `invalidate_all() -> None` — clears the entire cache. No TTL, no size limit. No mill imports.
- **Commit:** `feat(wiki): add _store.py in-process content cache`

## Batch Tests

`verify: null` — pure logic with no runnable entry point yet; tests are written in Batch 6 (`test-wiki-store.py`). The implementer should manually verify the module imports cleanly: `PYTHONPATH=plugins/mill/scripts python -c "from wiki import _store; s = _store.Store(); print('ok')"`.
