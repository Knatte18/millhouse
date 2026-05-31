# Batch: Server and Client Protocol

```yaml
task: Replace manual layer letters with depends_on + isolated flags
batch: Server and Client Protocol
number: 4
cards: 7
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-wiki-protocol.py test-wiki-daemon.py
depends-on: [1, 2, 3]
```

## Batch Scope

Wire the new ops and error types into `wiki/_server.py` and `wiki/_client.py`. The server gains `OP_SET_DEPS` and `OP_MIGRATE_DEPS` handlers, maps store `ValueError` to `ERR_VALIDATION`, bumps its protocol version constant, and enriches `list_tasks_brief` rows with the derived `layer` key. The client gains `set_deps()` and `migrate_deps()` functions, drops the `group=` kwarg from `upsert_task`, adds the new schema kwargs, and raises `WikiValidationError` on `ERR_VALIDATION` responses.

TDD order: write Card 15 (tests) first; implement Cards 16–21 to make them pass.

## Cards

### Card 15: Test additions for server and client protocol

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_server.py`
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/_store.py`
  - `plugins/mill/scripts/wiki/_render.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-protocol.py`
  - `plugins/mill/unit_tests/test-wiki-daemon.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Write these test cases before implementing Cards 16–21. In `test-wiki-protocol.py`, add: (a) **ERR_VALIDATION → WikiValidationError**: via `WIKI_DAEMON_INPROCESS`, upsert a task with a dangling `depends_on`; assert `WikiValidationError` is raised by the client wrapper. (b) **set_deps wrapper round-trip**: insert two tasks; call `wiki._client.set_deps(wiki_path, "A", ["B"])`; verify no exception and the store reflects the change. (c) **OP_SET_DEPS unknown slug raises WikiValidationError**: call `set_deps` with a nonexistent slug; assert `WikiValidationError`. In `test-wiki-daemon.py`, add: (d) **OP_SET_DEPS round-trip via handle_request**: call `handle_request({op: OP_SET_DEPS, payload: {slug, depends_on}})` directly on a WikiServer instance (WIKI_DAEMON_SKIP_GIT=1); assert `ok: True` and the store is updated. (e) **OP_MIGRATE_DEPS round-trip**: insert a task with `group="Z"` by calling `wiki_server._store._db.insert({...})` directly (bypassing `upsert_task` validation, which rejects `group` keys post-Batch-2); call `handle_request({op: OP_MIGRATE_DEPS, payload: {}})` with WIKI_DAEMON_SKIP_GIT=1; assert `ok: True` and the task now has `isolated==True` and no `group` key. (f) **list_tasks_brief enriched with layer**: insert tasks A (no deps) and B (depends_on A) via the daemon; call `handle_request({op: OP_LIST_TASKS_BRIEF, payload: {}})` with WIKI_DAEMON_SKIP_GIT=1; assert each row has a `layer` key; assert A's layer is "A" and B's layer is "B". (g) **Orphan cleanup regression**: insert a task with a body (proposal), commit via daemon (WIKI_DAEMON_SKIP_PUSH=1); then remove the task via `OP_REMOVE_TASK`; assert the `proposal-<slug>.md` file no longer exists in the wiki path. If this test passes with the existing code, it is a green regression guard; if it fails, fix `_render_and_commit_all` accordingly.
- **Commit:** `test(protocol): server/client round-trip tests for set_deps, migrate_deps, validation, enriched brief, orphan cleanup`

### Card 16: _server.py: dispatch OP_SET_DEPS and OP_MIGRATE_DEPS

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_server.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Import `OP_SET_DEPS` and `OP_MIGRATE_DEPS` from `wiki` at the top of `_server.py` (alongside the existing `OP_*` imports). In `WikiServer.handle_request`, add two new dispatch branches: `elif op == OP_SET_DEPS: return self._handle_set_deps(payload)` and `elif op == OP_MIGRATE_DEPS: return self._handle_migrate_deps(payload)`.
- **Commit:** `feat(server): dispatch OP_SET_DEPS and OP_MIGRATE_DEPS`

### Card 17: _server.py: add _handle_set_deps and _handle_migrate_deps

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_store.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_server.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `WikiServer._handle_set_deps(self, payload: dict) -> dict`. Extract `slug = payload.get("slug")` and `depends_on = payload.get("depends_on", [])`. Call `self._store.set_deps(slug, depends_on)`. Call `self._render_and_commit_all(slug_for_msg=slug)`. Return `{FIELD_OK: True}` on success. Catch `ValueError` → return `{FIELD_OK: False, FIELD_ERROR_TYPE: ERR_VALIDATION, FIELD_ERROR: str(e)}`. Catch `WikiPushError` → return `{FIELD_OK: False, FIELD_ERROR_TYPE: ERR_PUSH_FAILED, FIELD_ERROR: str(e)}`. Add `WikiServer._handle_migrate_deps(self, payload: dict) -> dict`. Call `self._store.migrate_group_to_deps()`. Call `self._render_and_commit_all(slug_for_msg="migrate-deps")`. Return `{FIELD_OK: True}`. Catch `WikiPushError` → `ERR_PUSH_FAILED`. Catch `Exception` → `ERR_PROTOCOL`.
- **Commit:** `feat(server): add _handle_set_deps and _handle_migrate_deps`

### Card 18: _server.py: map ValueError to ERR_VALIDATION and set version 3

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_server.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Import `ERR_VALIDATION` from `wiki` at the top. In `_handle_upsert_task`, `_handle_upsert_tasks_batch`, and `_handle_merge_tasks`, add a `except ValueError as e:` branch before the bare `except Exception as e:` branch that returns `{FIELD_OK: False, FIELD_ERROR_TYPE: ERR_VALIDATION, FIELD_ERROR: str(e)}`. Set `WikiServer._protocol_version = 3` (change from 2). Import `ERR_VALIDATION` alongside the other `ERR_*` imports.
- **Commit:** `feat(server): map ValueError to ERR_VALIDATION, set protocol version 3`

### Card 19: _server.py: enrich list_tasks_brief with derived layer

- **Context:**
  - `plugins/mill/scripts/wiki/_render.py`
  - `plugins/mill/scripts/wiki/_store.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_server.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Import `compute_layers` from `wiki._render` at the top of `_server.py`. In `WikiServer._handle_list_tasks_brief`, after `tasks = self._store.list_tasks_brief()`, call `layer_map = compute_layers(self._store.all_tasks())` and then for each row in `tasks` merge in `row["layer"] = layer_map.get(row["slug"], "A")`. The `compute_layers` call uses `self._store.all_tasks()` (the full record set, including body/brief fields) to ensure the algorithm has all required fields. The store's `list_tasks_brief` returns the raw fields; the server enriches with the derived `layer` before returning.
- **Commit:** `feat(server): enrich list_tasks_brief rows with derived layer from compute_layers`

### Card 20: _client.py: update upsert_task, add set_deps and migrate_deps

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_client.upsert_task`: remove `group: str | None = None` parameter; add `depends_on: list[str] | None = None`, `isolated: bool | None = None`, `deferred: bool | None = None` parameters. In the payload construction block, attach these three to the payload only when not `None` (following the existing pattern for `title`, `brief`, etc.). Remove the `if group is not None: payload["group"] = group` line. Update the docstring to reflect the new parameters. Add `set_deps(wiki_path: Path, slug: str, depends_on: list[str]) -> None`: build payload `{"slug": slug, "depends_on": depends_on}`, dispatch with `OP_SET_DEPS`; raise `WikiValidationError` on `ERR_VALIDATION`, `WikiPushError` on `ERR_PUSH_FAILED`, `WikiProtocolError` otherwise. Import `OP_SET_DEPS`, `OP_MIGRATE_DEPS`, `ERR_VALIDATION`, `WikiValidationError` from `wiki` at the top (all four are needed by the functions in this card and Card 21). Add `migrate_deps(wiki_path: Path) -> None`: dispatch `OP_MIGRATE_DEPS` with empty payload; raise `WikiPushError` on `ERR_PUSH_FAILED`, `WikiProtocolError` otherwise.
- **Commit:** `feat(client): drop group= from upsert_task, add depends_on/isolated/deferred, set_deps, migrate_deps`

### Card 21: _client.py: add WikiValidationError branch to mutating wrappers

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `upsert_task`, `upsert_tasks_batch`, `merge_tasks`, and `set_deps` error-handling blocks, add `if error_type == ERR_VALIDATION: raise WikiValidationError(resp.get(FIELD_ERROR, ""))` before the final `raise WikiProtocolError(...)` fallback. Import `ERR_VALIDATION` and `WikiValidationError` from `wiki` (already added in Card 20). Update the docstrings' `Raises:` sections to include `WikiValidationError: Invalid task data.`.
- **Commit:** `feat(client): raise WikiValidationError on ERR_VALIDATION responses`

## Batch Tests

`test-wiki-protocol.py` verifies ERR_VALIDATION → WikiValidationError and new client functions. `test-wiki-daemon.py` verifies the two new ops round-trip through handle_request, list_tasks_brief enrichment, and orphan cleanup. Both test files use `WIKI_DAEMON_INPROCESS=1` / `WIKI_DAEMON_SKIP_GIT=1` / `WIKI_DAEMON_SKIP_PUSH=1` as appropriate.
