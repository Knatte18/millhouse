# Batch: Protocol Constants

```yaml
task: Replace manual layer letters with depends_on + isolated flags
batch: Protocol Constants
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-protocol.py
depends-on: []
```

## Batch Scope

Add the new protocol constants (`OP_SET_DEPS`, `OP_MIGRATE_DEPS`, `ERR_VALIDATION`, `WikiValidationError`) and bump `PROTOCOL_VERSION` from 2 to 3 in `wiki/__init__.py`. Update `test-wiki-protocol.py` to assert the new version and verify the new symbols exist. This batch produces no behaviour change — the symbols are wired up by batches 4 and 5. It must land first because batch 4 imports them.

TDD order: write Card 1 (tests) first; implement Cards 2–3 to make them pass.

## Cards

### Card 1: Update test-wiki-protocol.py for new version and symbols

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-protocol.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Write these test cases in `test-wiki-protocol.py` (TDD: add before implementing Cards 2–3 so they fail first): (a) `PROTOCOL_VERSION == 3` (update any existing assertion from `== 2`); (b) `OP_SET_DEPS == "set_deps"` exists and is importable; (c) `OP_MIGRATE_DEPS == "migrate_deps"` exists and is importable; (d) `ERR_VALIDATION == "validation_error"` exists and is importable; (e) `WikiValidationError` is a subclass of `WikiError` and can be raised and caught as `WikiError`.
- **Commit:** `test(wiki): assert PROTOCOL_VERSION=3 and new protocol symbols`

### Card 2: Add new op constants and ERR_VALIDATION to wiki/__init__.py

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `OP_SET_DEPS = "set_deps"` and `OP_MIGRATE_DEPS = "migrate_deps"` alongside the existing `OP_*` constants. Add `ERR_VALIDATION = "validation_error"` alongside the existing `ERR_*` constants.
- **Commit:** `feat(wiki): add OP_SET_DEPS, OP_MIGRATE_DEPS, ERR_VALIDATION constants`

### Card 3: Add WikiValidationError and bump PROTOCOL_VERSION

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `class WikiValidationError(WikiError)` with docstring `"Invalid task data rejected by the store."` after the existing exception classes. Change `PROTOCOL_VERSION: int = 2` to `PROTOCOL_VERSION: int = 3`.
- **Commit:** `feat(wiki): add WikiValidationError, bump PROTOCOL_VERSION to 3`

## Batch Tests

`test-wiki-protocol.py` covers all five new assertions. The test file already uses `WIKI_DAEMON_INPROCESS=1` for server-level tests; the new symbol assertions are import-level and do not require a running server.
