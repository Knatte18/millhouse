# Batch: Server Integration

```yaml
task: Migrate wiki task store to TinyDB
batch: Server Integration
number: 2
cards: 2
verify: null
depends-on: [1]
```

## Batch Scope

This batch modifies `wiki/_server.py` to use the new TinyDB-backed `Store` from batch 1. Two cards cover the read and write paths respectively. The public API exposed by `wiki/_client.py` is unchanged — only internal server behaviour changes. `wiki/_sync.py` and `wiki/_client.py` are not modified. After this batch the daemon is fully functional with TinyDB backing; tests come in batch 3.

## Cards

### Card 5: Update _handle_read — post-pull repopulation

- **Context:**
  - `plugins/mill/scripts/wiki/_store.py`
  - `plugins/mill/scripts/wiki/_sync.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_server.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `WikiServer.__init__`: change `self._store = Store()` to `self._store = Store(wiki_path / "tasks.json")`. Remove the import of the old `Store` class signature if the constructor changed.

  In `_handle_read`: replace the existing lazy-refresh block that calls `self._store.invalidate_all()` with the following sequence:
  1. `pull(self._wiki_path)` — unchanged.
  2. Read `Home.md` from disk: `disk_content = (self._wiki_path / "Home.md").read_text("utf-8")`.
  3. `self._store.set("Home.md", disk_content)` — repopulates TinyDB from the pulled file.
  4. Update `self._last_pull = time.monotonic()`.
  Wrap the disk read in a try/except `FileNotFoundError` — if `Home.md` does not exist on disk, skip the `set` call (leave store uninitialized). Log the `WikiPushError` from `pull()` as a warning and continue serving from cache (same as current behaviour).

  The cache-miss path (`if hit is not None` / disk read) is unchanged except: when `rel_path == "Home.md"` and the store returns `None` (uninitialized), fall through to the disk-read path, read `Home.md`, call `self._store.set("Home.md", content)`, then return the `self._store.get("Home.md")` result (so the returned content is the rendered version, not the raw disk content).

  Remove the call to `self._store.invalidate_all()` everywhere in `_handle_read`.
- **Commit:** `feat(wiki): _server read path -- repopulate TinyDB from disk after pull`

### Card 6: Update _handle_write — new write path sequence

- **Context:**
  - `plugins/mill/scripts/wiki/_store.py`
  - `plugins/mill/scripts/wiki/_render.py`
  - `plugins/mill/scripts/wiki/_sync.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_server.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Replace the body of `_handle_write` with the following sequence. Preserve all existing error-response shapes (`FIELD_OK`, `FIELD_ERROR_TYPE`, `FIELD_ERROR`).

  1. **Pull:** call `pull(self._wiki_path)`. On `WikiPushError`, return `{FIELD_OK: False, FIELD_ERROR_TYPE: ERR_PUSH_FAILED, FIELD_ERROR: str(e)}`.

  2. **Repopulate TinyDB from pulled state:** if `Home.md` is in `files_payload` (a write is incoming for it), or if `self._store.get("Home.md") is None` (store uninitialized), read `Home.md` from disk and call `self._store.set("Home.md", disk_content)`. Wrap in try/except `FileNotFoundError` — skip if absent. Update `self._last_pull = time.monotonic()`.

  3. **CAS check** for each `rel_path` in `files_payload`:
     - Call `path_guard(rel_path)` — on `WikiPathError`, return path error response.
     - Compute `current_hash`: for `"Home.md"`, call `self._store.get("Home.md")` and take `[1]` (the hash); if `get` returns `None`, use `""`. For other paths, use `self._store.get(rel_path)[1]` if cached, else read from disk and hash, else `""`.
     - Compare `base_hash` from `files_payload[rel_path][FIELD_BASE_HASH]` against `current_hash`. If mismatch: return `{FIELD_OK: False, FIELD_ERROR_TYPE: ERR_CONFLICT, FIELD_ERROR: f"conflict on {rel_path}"}`.

  4. **atomic_write** each client file: call `atomic_write(self._wiki_path, rel_path, new_content)` for each entry. On `OSError`, return push-failed error response.

  5. **Update TinyDB:** for each `rel_path` in `files_payload`: call `self._store.set(rel_path, new_content)` (where `new_content` is `files_payload[rel_path][FIELD_NEW_CONTENT]`). For `"Home.md"` this updates TinyDB; for other paths this updates the file cache.

  6. **Render:** call `from wiki._render import render; rendered = render(self._store.all_tasks())`. Write each file in `rendered` to disk via `atomic_write(self._wiki_path, rel_path, content)` — this overwrites the `Home.md` written in step 4 with the TinyDB-rendered version, and writes `_Sidebar.md` and any `proposal-*.md` files.

  7. **Commit:** assemble `commit_paths = list(files_payload.keys()) + list(rendered.keys()) + ["tasks.json"]`. Deduplicate. Call `commit_push(self._wiki_path, commit_paths, message)`. On `WikiPushError`, return push-failed error response.

  8. **Invalidate non-Home.md cache entries** that were written: for `rel_path` in `files_payload` where `rel_path != "Home.md"`, call `self._store.invalidate(rel_path)` (clears stale file-cache entry; the fresh content is in the dict from step 5 but calling invalidate is safe since it only affects non-Home.md paths).

  9. Return `{FIELD_OK: True}`.

  Remove the old `self._store.invalidate_all()` call that previously followed `pull()` in `_handle_write`. Remove the old `self._store.invalidate(rel_path)` loop at the end (replaced by step 8 above, which is more precise).

  Import `render` from `wiki._render` at the top of the file (add to existing imports). Import `Store` from `wiki._store` (update import to match new constructor signature).
- **Commit:** `feat(wiki): _server write path -- TinyDB update, render, and commit all artifacts`

## Batch Tests

verify is null — unit and integration tests are written in batch 3. To smoke-test: start the daemon against a test wiki repo and call `wiki._client.read("Home.md")`.
