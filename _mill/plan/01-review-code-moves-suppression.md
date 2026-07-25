# Batch: review-code-moves-suppression

```yaml
task: Batch review/verify pipeline doesn't account for cross-batch state changes
batch: review-code-moves-suppression
number: 1
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-code-flow.py
depends-on: []
```

## Batch Scope

Fixes GitHub #686: `_review_code.py`'s holistic `prepare()` discards the `sources` half of `compute_moves_union()`'s return value instead of merging it into `deletes_union`, so a batch card's `Context:` ref pointing at a path a later batch relocates via `Moves:` hard-fails `resolve_ref_paths` with `ReviewError` instead of being silently suppressed the same way an already-deleted path is. This batch is fully self-contained: it edits one function in one file and adds one regression test, with no dependency on any other batch in this plan. No external interface — the fix is purely internal to `prepare()`'s ref-resolution call.

## Cards

### Card 1: Merge moves-sources into deletes_union in `_review_code.py`'s `prepare()`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/scripts/_review_code.py`'s `prepare()` function, change the line `_, moves_targets_union = compute_moves_union(plan_dir)` (currently around line 279) to capture both halves of the tuple, e.g. `moves_sources_union, moves_targets_union = compute_moves_union(plan_dir)`. Then change the immediately-following `resolve_ref_paths(...)` call's `deletes_union=deletes_union` keyword argument to `deletes_union=deletes_union | moves_sources_union`. No other lines in `prepare()` change — `moves_targets_union` is already consumed correctly further down (the `moves_targets_on_disk = resolve_existing_paths(...)` block) and must be left untouched. Do not touch `_review_plan.py` — its two `compute_moves_union()` call sites (around lines 354 and 668) already correctly keep both halves and are out of scope for this task.
- **Commit:** `fix(review-code): merge moves-sources into deletes_union so relocated Context: refs are suppressed, not hard-failed`

## Batch Tests

`verify:` runs `test-review-code-flow.py`, which already exercises `prepare()`'s ref-resolution path end-to-end (imports `run`/`finalize` from `_review_code`, drives fixtures via `_test_helpers`). Add a new test function to this file, following its existing fixture style: build a minimal plan fixture with batch A whose a card's `Context:` references a path (e.g. `` `docs/old-name.md` ``), and batch B (later in the plan, e.g. depends on batch A) whose a card's `Moves:` relocates that exact path (e.g. `` `docs/old-name.md` -> `docs/new-name.md` `` — with `docs/new-name.md` present on disk in the fixture, `docs/old-name.md` absent). Assert `prepare()` no longer raises `ReviewError` for the stale `Context:` ref, and that the resolved source-file list omits the moved-away path (mirroring today's existing behavior for an equivalent `Deletes:`-suppressed path — add or reuse a comparable existing test case as the baseline for "what suppression looks like" if one already exists in this file). No other test file is affected; `verify:` is scoped to this one file per this batch's narrow blast radius.
