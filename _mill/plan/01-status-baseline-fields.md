# Batch: status-baseline-fields

```yaml
task: 'compute_baseline: use the task worktree''s own pre-edit state, not a parent-branch checkout'
batch: status-baseline-fields
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py
depends-on: []
```

## Batch Scope

This batch prepares the `status.md` field surface the rest of the plan depends on: it adds the `module_verify_baseline_signatures` list accessor pair that the eager module-wide capture (batch 3) and the merge-in recompute (batch 5) need to persist/seed a pair-cache from. `_status.py` has no import-time coupling to `_verify_baseline.py`, so this batch could run standalone, but batch 3 calls the new accessors, so it is ordered before it.
This batch deliberately does NOT delete the now-dead `get_baseline_parent_sha`/`set_baseline_parent_sha` scalar accessor pair, even though `compute_baseline`'s no-checkout redesign makes them dead. Their only reader — `_implementer_common._run_verify_gates`'s on-demand-compute prelude, at `baseline_parent_sha = _status.get_baseline_parent_sha(status_path)` — calls it with NO surrounding `try`/`except` (unlike the adjacent `compute_batch_baseline_on_demand` call, which is wrapped), and that reader survives until batch 4 deletes it. Deleting the accessor here in batch 1 would leave every batch between this one and batch 4 — including this very plan's own batch 1/2/3 verify replays, driven through this same `_run_verify_gates` code path — one first-attempt verify failure away from an unguarded `AttributeError` crash instead of the intended graceful strict-gating degradation. The accessor pair is deleted in batch 4 instead, in the same batch (and the same card-ordering position, immediately after its caller is removed) that removes the last read of it — see batch 4's Card 27.

## Cards

### Card 2: Add module_verify_baseline_signatures accessor pair

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `get_module_verify_baseline_signatures(status_path: Path) -> list[str] | None`, mirroring `get_module_verify_baseline`'s implementation shape exactly (`_require_path(status_path, "get_module_verify_baseline_signatures")`; `data = read(status_path)`; `return data.get("module_verify_baseline_signatures")`).
  Add `set_module_verify_baseline_signatures(status_path: Path, value: list[str]) -> None`, mirroring `set_module_verify_baseline`'s insert-in-place-or-append-after-`parent:`-row pattern (same `_split_fences`/`_YAML_FENCE` scan, same "rewrite the existing `module_verify_baseline_signatures:` row in place if present, else insert immediately after `parent:`" structure) but serializing `value` as a flow-sequence via `yaml.safe_dump(value, default_flow_style=True, width=10**9).strip()` rather than `quote_scalar` (which is string-only). The explicit `width=10**9` is load-bearing: PyYAML's default 80-column `best_width` would wrap a realistic multi-signature list across physical lines, and every other reader/writer of this top yaml block (`set_module_verify_baseline`'s in-place rewrite, `clear_module_verify_baseline`'s `del lines[i]`, `read`'s whole-block `yaml.safe_load`) assumes one field is exactly one physical line.
  Update `clear_module_verify_baseline` to also delete the `module_verify_baseline_signatures:` row when present, in the same call — loop the existing single-row-delete scan over both `module_verify_baseline:` and `module_verify_baseline_signatures:` patterns (or call the existing per-pattern delete logic twice) so both rows are removed together; the two fields must never go out of sync, since a stale signature set paired with a cleared verdict would seed a later dedup from a run that no longer has a corresponding verdict.
  Update the module's top `Public API:` docstring block: add `get_module_verify_baseline_signatures(status_path) -> list[str] | None` and `set_module_verify_baseline_signatures(status_path, value) -> None` (placed alongside the existing `get/set/clear_module_verify_baseline` lines).
- **Commit:** `feat(_status): add module_verify_baseline_signatures accessor pair`

### Card 3: Update test-status.py for the accessor changes

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Leave the existing "--- baseline_parent_sha tests ---" block and the `get_baseline_parent_sha`/`set_baseline_parent_sha` imports untouched in this card — per this batch's own Batch Scope note, the accessor pair itself is not deleted until batch 4, and its test coverage is deleted there too (batch 4's Card 27), alongside the function deletion, not here.
  In the "--- module_verify_baseline tests ---" block, add: (a) round-trip coverage for `get_module_verify_baseline_signatures`/`set_module_verify_baseline_signatures` mirroring the existing `module_verify_baseline` scalar accessors' own insert-in-place-vs-append assertions, including an empty list `[]` surviving a round-trip as a present-but-empty field (distinct from the key being absent); (b) a signature list long enough that a naive `yaml.safe_dump` without a `width` override would wrap it across multiple physical lines — assert it instead writes as exactly one physical line, and that a subsequent `set` then `clear_module_verify_baseline` then `read` round-trip on that value leaves `status.md` fully parseable (the regression guard for the line-stranding bug this would otherwise cause on every later `_status` read); (c) `clear_module_verify_baseline` now also clears `module_verify_baseline_signatures` in the same call — assert both fields are absent after one `clear_module_verify_baseline` call that previously had both set.
  Add `get_module_verify_baseline_signatures` and `set_module_verify_baseline_signatures` to the `from _status import (...)` block.
- **Commit:** `test(_status): drop baseline_parent_sha coverage, add signatures accessor coverage`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-status.py` alone via `run-all.py --only` — the only file this batch's cards edit outside `_status.py` itself, and the file that directly exercises every accessor this batch adds or removes.
