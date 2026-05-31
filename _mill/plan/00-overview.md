# Plan: Replace manual layer letters with depends_on + isolated flags

```yaml
task: Replace manual layer letters with depends_on + isolated flags
slug: task-deps-and-isolation
approved: true
started: 20260531-075409
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: Protocol Constants
    file: 01-protocol-constants.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-protocol.py
  - number: 2
    name: Store Schema and Validation
    file: 02-store-schema-validation.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-store.py
  - number: 3
    name: Render compute_layers and Helpers
    file: 03-render-compute-layers.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-render.py
  - number: 4
    name: Server and Client Protocol
    file: 04-server-client-protocol.md
    depends-on: [1, 2, 3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-wiki-protocol.py test-wiki-daemon.py
  - number: 5
    name: Consumer Scripts
    file: 05-consumer-scripts.md
    depends-on: [4]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-spawn-core.py test-millpy-spawn.py
```

## Shared Decisions

### Decision: store-raises-valueerror

- **Decision:** `wiki/_store.py` raises plain `ValueError` on all validation failures. `wiki/_server.py` catches `ValueError` from the store and returns `ERR_VALIDATION` in the response envelope. `wiki/_client.py` catches `ERR_VALIDATION` and raises `WikiValidationError`.
- **Rationale:** The store is the only layer that sees the full task set atomically; it validates there. The server is the protocol layer; it translates Python exceptions to wire errors. The client is the API surface; it raises typed exceptions so callers distinguish bad-input from transport faults.
- **Applies to:** batches 2, 4.

### Decision: ascii-error-strings

- **Decision:** All error message strings that surface to operators (validation errors, log output, print statements) must use ASCII only. Use ` -- ` not em-dash, ` -> ` not arrow. This includes strings raised by `_validate_write` in `_store.py`, since they propagate through the server to the client and then to the operator.
- **Rationale:** Windows cp1252 crashes on non-ASCII stdout.
- **Applies to:** all batches.

### Decision: missing-fields-default

- **Decision:** `compute_layers`, `render_order`, and `extended_title` use `.get()` with defaults for `depends_on` (`[]`), `isolated` (`False`), `deferred` (`False`), `status` (`None`). Task dicts that predate the migration (missing the new fields) behave as if they have no deps and are not isolated/deferred.
- **Rationale:** Consumers call these helpers with `list_tasks_brief` rows that may include migrated and un-migrated data during the transition window.
- **Applies to:** batches 3, 5.

### Decision: tinydb-delete-for-migration

- **Decision:** `Store.migrate_group_to_deps()` uses `tinydb.operations.delete("group")` inside `self._db.update(...)` to drop the `group` key while leaving `doc_id` and `id` untouched. Never clear-and-reinsert to remove a key; that re-keys doc_ids.
- **Rationale:** Preserving `doc_id` and the task `id` field is required by the migration spec. TinyDB's `delete` operation is the precise tool for field removal without re-keying.
- **Applies to:** batch 2.

### Decision: tdd-order

- **Decision:** In each batch, write the test additions first (as failing tests), then implement to make them pass. The `verify:` command must be green before the batch commit.
- **Rationale:** Tests document the required behavior exactly; writing them first prevents spec drift.
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/scripts/_spawn_core.py`
- `plugins/mill/scripts/millpy-inspect.py`
- `plugins/mill/scripts/millpy-status.py`
- `plugins/mill/scripts/millpy-wiki-migrate-deps.py`
- `plugins/mill/scripts/wiki/__init__.py`
- `plugins/mill/scripts/wiki/_client.py`
- `plugins/mill/scripts/wiki/_render.py`
- `plugins/mill/scripts/wiki/_server.py`
- `plugins/mill/scripts/wiki/_store.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
- `plugins/mill/unit_tests/test-spawn-core.py`
- `plugins/mill/unit_tests/test-wiki-daemon.py`
- `plugins/mill/unit_tests/test-wiki-protocol.py`
- `plugins/mill/unit_tests/test-wiki-render.py`
- `plugins/mill/unit_tests/test-wiki-store.py`
