# Batch: review-common-parse-deletes

```yaml
task: Batch review/verify pipeline doesn't account for cross-batch state changes
batch: review-common-parse-deletes
number: 2
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-common.py
depends-on: []
```

## Batch Scope

Prerequisite for batch `iter-batch-verifies-cross-batch-filter`: adds a standalone per-batch-file `parse_deletes(batch_path) -> set[str]` function to `_review_common.py`, mirroring the existing standalone `parse_moves(batch_path)` (line 551). Today only `compute_deletes_union()` (line 666) can extract `Deletes:` tokens, and it does so by inlining the parsing logic across an entire `plan_dir` rather than exposing a per-file primitive — batch `iter-batch-verifies-cross-batch-filter` needs the per-file version to build a per-batch (not unioned) removal map. This batch also refactors `compute_deletes_union()` to call the new function internally, eliminating the duplicated inline logic. External interface the next batch consumes: `parse_deletes(batch_path: Path) -> set[str]`, importable from `_review_common`.

## Cards

### Card 2: Add `parse_deletes()` to `_review_common.py`; refactor `compute_deletes_union()` to use it

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new module-level function `parse_deletes(batch_path: Path) -> set[str]` to `plugins/mill/scripts/_review_common.py`, placed near `parse_moves` (line 551) for discoverability. Its body is the per-batch-file token-extraction logic currently inlined inside `compute_deletes_union()`'s loop body (lines 681-710: read the file, split into lines, scan for `_RE_REFS_HEADER` matches where `m.group(1) == "Deletes"`, extract inline backtick tokens or multi-line `_RE_REFS_SUB` sub-bullets, filter case-insensitive `"none"`) — extract this exact logic into `parse_deletes`, operating on a single `batch_path` and returning the resulting `set[str]` (not accumulating into an outer `deletes` set — that's the caller's job now). Give it a docstring in the same style as `parse_moves`'s (Args/Returns, notes that malformed/absent `Deletes:` headers simply contribute nothing, never raises except from `read_text`'s own I/O errors). Then refactor `compute_deletes_union(plan_dir)` to call `parse_deletes(batch_path)` per batch file and union the results (`deletes |= parse_deletes(batch_path)` inside the existing `for batch_path in sorted(plan_dir.glob("??-*.md"))` loop, after the existing `00-overview.md` skip), removing the now-duplicated inline parsing block. `compute_deletes_union`'s public signature, docstring, and external behavior are unchanged — this is a pure internal refactor. Do not touch `compute_creates_union` (line 618) or `parse_batch_refs` (line 494) — structurally similar but out of scope for this task; only `Deletes:` parsing is being extracted.
- **Commit:** `refactor(review-common): extract parse_deletes() from compute_deletes_union's inline logic`

## Batch Tests

`verify:` runs the full `test-review-common.py` file (not a `--only` scope — this batch touches a shared helper (`compute_deletes_union`) with ~9 existing test functions around lines 1360-1440 covering nonexistent plan_dir, inline form, multi-line bullet form, `none`/`None`/`NONE` sentinel filtering, cross-batch de-duplication, absent-on-some-cards, and `00-overview.md` exclusion — running the whole file is the cheapest way to confirm the refactor changes zero observable behavior). Add new test functions for `parse_deletes`, mirroring `parse_moves`'s existing per-function test shape (single-line inline form, multi-line bullet form, `none` sentinel returns empty set, `Deletes:` mixed among other card fields, malformed sub-bullet tolerated without raising) — operate on a single batch file via `parse_deletes(batch_path)` directly, not a `plan_dir`. Do not modify any of the existing `compute_deletes_union` test bodies or assertions — they are the regression guard that the refactor is behavior-preserving; only their internal call path changes, not their expected outputs.
