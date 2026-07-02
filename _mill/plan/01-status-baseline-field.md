# Batch: status-baseline-field

```yaml
task: "Fix agent-mode dispatch races and pipeline gaps"
batch: status-baseline-field
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py
depends-on: []
```

## Batch Scope

Add a small task-scoped `module_verify_baseline` field to `status.md`'s top YAML block, with get/set/clear helpers in `_status.py`. This is the persistence layer the `#590` baseline-aware verify gate (batch 3) reads and writes; it has no dependency on any other batch and can be implemented and tested in complete isolation from the verify-gate logic itself. The field holds one of three states: unset (`None` — no baseline computed yet), `"clean"` (parent branch's own module-wide verify passes), or `"pre-existing-failures"` (parent branch's own module-wide verify already fails, so the per-batch module-wide gate should be skipped for the rest of the task). No existing `_status.py` helper fits: `update_field` requires the key to already exist in the YAML block (raises `ValueError` otherwise), and this field does not exist in `status-discussing.md`'s template, so the new helpers must insert-or-rewrite the row themselves — mirroring the existing insert-if-absent / rewrite-if-present pattern `set_blocked` (`_status.py:223-298`) already uses for `blocked_reason:`.

## Cards

### Card 1: add module_verify_baseline get/set/clear helpers to _status.py

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add three new public functions to `_status.py`, placed after `set_blocked` (after line 298) and before `append_phase`, following the module's existing docstring style:
  - `get_module_verify_baseline(status_path: Path) -> str | None` — reads the top YAML block via the existing `read()` function and returns `data.get("module_verify_baseline")` (which is `None` when the key is absent or explicitly `null`). Do not raise on a missing key — `None` is the expected "not yet computed" state, not an error.
  - `set_module_verify_baseline(status_path: Path, value: str) -> None` — `value` must be the literal string `"clean"` or `"pre-existing-failures"`; raise `ValueError` for any other value (mirror `set_batch_field`'s `key`/`state` validation style at `_status.py:820-827`). Locate the top YAML block via `_split_fences(text, _YAML_FENCE)` (same helper `update_field` and `set_blocked` already use). If a `module_verify_baseline:` row already exists in the block, rewrite it in place (same line-replace mechanics as `update_field`, `_status.py:207-219`). If absent, insert a new `module_verify_baseline: <value>` row immediately after the `parent:` row (mirror `set_blocked`'s insert-after-`phase:` mechanics at `_status.py:283-288`, but insert after `parent:` instead since that is the field's natural neighbor in the template's field ordering). Write the value through `_yaml_writer.quote_scalar` for consistency with every other string field in this module.
  - `clear_module_verify_baseline(status_path: Path) -> None` — locates and removes the `module_verify_baseline:` row entirely if present (same discovery scan as `set_module_verify_baseline`, but deletes the line rather than rewriting it — mirror `append_phase`'s `blocked_reason:` deletion mechanics at `_status.py:356-364`). A no-op (not an error) when the row is already absent — this function must be safe to call unconditionally before every baseline recompute, including the very first one where the field has never been written.

  Update the module docstring's "Public API" list (`_status.py:18-35`) to add these three new function signatures in the same one-line style as the existing entries.
- **Commit:** `feat(_status): add module_verify_baseline get/set/clear helpers`

### Card 2: unit tests for module_verify_baseline helpers

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add test cases to `test-status.py` (append after the existing last case, following the file's existing `assert`-based case style — see e.g. the `phase_entry_timestamp` cases near the end of the file) covering:
  - `get_module_verify_baseline` returns `None` on a freshly-rendered status.md (via `_status.render_initial`) that has never had the field set.
  - `set_module_verify_baseline(status_path, "clean")` on a fresh file inserts the row; a subsequent `get_module_verify_baseline` returns `"clean"`.
  - `set_module_verify_baseline` called a second time with `"pre-existing-failures"` rewrites the existing row in place (not a duplicate row) — assert `get_module_verify_baseline` returns the new value and the raw file text contains exactly one `module_verify_baseline:` line.
  - `set_module_verify_baseline(status_path, "bogus")` raises `ValueError`.
  - `clear_module_verify_baseline` after a prior `set_module_verify_baseline("clean")` removes the row; `get_module_verify_baseline` then returns `None`.
  - `clear_module_verify_baseline` on a file that never had the field set is a no-op (does not raise, file content unchanged).
  - Use a `tempfile.TemporaryDirectory()` + `_status.render_initial(...)`-written fixture file, matching the fixture pattern already used elsewhere in this test file (see the existing `render_initial`-based setup blocks).
- **Commit:** `test(_status): cover module_verify_baseline get/set/clear helpers`

## Batch Tests

`verify:` runs `test-status.py` only — the new helpers and their tests are fully self-contained in that one file plus `_status.py`, so no broader suite run is needed.
