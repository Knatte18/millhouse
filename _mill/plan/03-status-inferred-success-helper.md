# Batch: status-inferred-success-helper

```yaml
task: 'mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)'
batch: status-inferred-success-helper
number: 3
cards: 2
verify: 'PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-status.py'
depends-on: []
```

## Batch Scope

`#781`: implements the one Python-side mechanism batch 1's cards 5-6 document calling — a new `_status.append_inferred_success_log(status_path, batch_name, round, timestamp)` helper in `plugins/mill/scripts/_status.py`, modeled directly on the existing `append_recovery_log`'s convention: lazily create a `## Inferred-success log` section in `status.md` on first use, append-only on every subsequent call, mirroring `## Tracked-file recovery log`'s own established pattern (a plain fenced-`text` append-only block, not a yaml list, structurally identical to `_find_recovery_log_block`/`append_recovery_log`).
This gives visibility into the finalize-side no-JSON commit-count recount's `"inferred": true` occurrences (currently silent) without changing that recount's own correctness — the recount already produces the right outcome; this batch only makes a protocol violation visible when it happens.
This batch has no dependency on batch 1 — batch 1's `SKILL.md` prose references this function by name but is documentation, not executable code that imports it; the two batches touch disjoint files (`_status.py`/`test-status.py` here vs. `mill-go/SKILL.md`/`harness-tool-contracts.md` there) and either can run first.
No batch-local decisions differ from `## Shared Decisions` in the overview.

## Cards

### Card 9: Add `_status.append_inferred_success_log` helper

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new module-level constant `_INFERRED_SUCCESS_LOG_HEADING = "## Inferred-success log"`, placed immediately alongside the existing `_RECOVERY_LOG_HEADING = "## Tracked-file recovery log"` and `_BATCHES_HEADING = "## Batches"` constants.
  Add a new private helper `_find_inferred_success_log_block(lines: list[str]) -> tuple[int, int, int, int] | None`, structurally identical to `_find_recovery_log_block` (same four-tuple return shape `(heading_idx, fence_open_idx, fence_close_idx, section_end_idx)`, same "returns `None` if the heading is absent" contract, same fenced-`` ```text `` body form) but scanning for `_INFERRED_SUCCESS_LOG_HEADING` instead of `_RECOVERY_LOG_HEADING`.
  Add a new public function:
  `append_inferred_success_log(status_path: Path, batch_name: str, round: int, timestamp: str) -> None`.
  Model its body directly on `append_recovery_log`'s body: `_require_path(status_path, "append_inferred_success_log")`; read and splitlines the file; build one new row as `f"{quote_scalar(timestamp)}  {batch_name}  round {round}"` (mirrors `append_recovery_log`'s `f"{quote_scalar(timestamp)}  {', '.join(restored_paths)}"` row shape, substituting this function's own fields); call `_find_inferred_success_log_block(lines)`; if `None` (section absent), append a new section at EOF with a leading blank separator when the last line is non-blank, then extend `lines` with `[_INFERRED_SUCCESS_LOG_HEADING, "", _TIMELINE_FENCE, new_row, "```"]` (reuse the existing `_TIMELINE_FENCE` constant — it is the plain ` ```text ` fence marker already used by `_find_recovery_log_block`/`append_recovery_log`, not specific to the Timeline section); otherwise (section present), insert the new row immediately before the located `fence_close_idx` — an append, never a whole-section replace, identical to `append_recovery_log`'s existing-block branch.
  Write the file back with `status_path.write_text("\n".join(lines) + "\n", encoding="utf-8")`, matching `append_recovery_log`'s own write call exactly.
  Give the new function a docstring in the same style as `append_recovery_log`'s (Args/Raises sections), explicitly stating: this function is the caller's explicit, separate audit-append step; the finalize-side no-JSON recount itself never calls this function or touches `status.md` — callers (mill-go's step 4(b) and step 6.5 call sites) call this helper themselves after inspecting the finalize envelope's `inferred` field.
- **Commit:** `feat(status): add append_inferred_success_log helper for #781 observability`

### Card 10: Unit tests for `append_inferred_success_log`

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `append_inferred_success_log` to the existing `from _status import (...)` import list at the top of the file, alongside the existing `append_phase`/`append_recovery_log` imports.
  Add a new test block mirroring the existing `--- append_recovery_log tests ---` block's structure and coverage (that block covers: section created lazily on first call, second-row appends without dropping the first, multi-value row formatting, non-disturbance of the Timeline/yaml blocks, and two `ValueError` raise cases for a missing/unterminated fence).
  Cover the equivalent cases for `append_inferred_success_log`: (1) `## Inferred-success log` section is created lazily on first call, on a status.md that has none; (2) a second call appends a new row without overwriting or dropping the first row; (3) the row contains the batch name and round number in the expected format; (4) calling it does not disturb the existing `## Timeline` block or the top yaml block's `phase:` field (confirm `phase:` is byte-identical before and after the call, since the function's docstring explicitly states it never touches `phase:`); (5) mirrors the `ValueError` case for a `## Inferred-success log` heading present with its fenced block missing/unterminated (same malformed-fence contract `_find_recovery_log_block`/`append_recovery_log` already enforce, applied here via `_find_inferred_success_log_block`/`append_inferred_success_log`).
  Follow this file's existing test-function naming and fixture conventions (in-memory/tempfile status.md fixtures, no real git/LLM, per the `plugins/mill/unit_tests/` module docstring convention) exactly as the neighboring `append_recovery_log` tests already do.
- **Commit:** `test(status): cover append_inferred_success_log lazy-section and append-only behavior`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-status.py` runs the full `test-status.py` file (including the new Card 10 tests alongside every pre-existing `_status.py` test) — this is a single-file, fast, in-memory test suite with no real git/LLM dependency, so running the whole file (rather than a `--only` subset) is proportionate and matches this file's own existing scope (it already tests every other `_status.py` function in one file).
