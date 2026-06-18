# Batch: review-discussion-nitcount

```yaml
task: "Fix agent error recovery, implementer/review false-success contracts, VS Code watcher, and plan-validator Deletes"
batch: "review-discussion-nitcount"
number: 3
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-discussion-flow.py
depends-on: []
```

## Batch Scope

Fixes issue #503: `millpy-review-discussion.py`'s finalize reports `nit_count: 0` in its JSON summary even when the review file contains `[NOTE]` findings. `finalize_scope` already computes the correct `nit_count` for discussion reviews, but `_review_discussion.py::finalize` drops it when constructing the returned `ReviewResult` (the code and plan review paths thread it through; only discussion omits it). One-line plumbing fix plus the missing regression test. Self-contained.

## Cards

### Card 3: Thread nit_count into discussion ReviewResult

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `_review_discussion.py`, in the `finalize(...)` function's success return (the `return ReviewResult(...)` built from `review_entry` after `finalize_scope` succeeds — NOT the `ReviewError` branch), add the keyword argument `nit_count=review_entry["nit_count"]` to the `ReviewResult(...)` constructor, alongside the existing `blocking_count=review_entry["blocking_count"]`. Mirror the pattern already used in `_review_code.py` (its finalize passes `nit_count=review_entry["nit_count"]`). Do not change the `ReviewError`/`verdict="ERROR"` branch.
  - In `test-review-discussion-flow.py`, add a `nit_count` assertion mirroring the existing `blocking_count` test: feed a discussion review body containing two `### [NOTE]` headings and zero `### [GAP]` headings through the same finalize/flow path the existing test uses, and assert the resulting summary has `nit_count == 2` and `blocking_count == 0`. Keep the existing `blocking_count`-from-`[GAP]` assertions intact.
- **Commit:** `fix(review-discussion): thread nit_count into finalize ReviewResult`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-review-discussion-flow.py` (standalone `__main__` runner), which exercises the discussion finalize flow including the new `nit_count` assertion. Scoped to the single test file because this batch touches only `_review_discussion.py`.
