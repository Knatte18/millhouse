I have completed thorough source-grounded verification of all three batches against the referenced files. Here is the review.

MILL_REVIEW_BEGIN
# Review: Fix discussion review round-cap, daemon cold-start, and nits-only no-op in finalize -- holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-30
```

## Findings

### [BLOCKING] Card 4's new test-marker.py functions are never executed
**Location:** Batch 2 / Card 4
**Issue:** `test-marker.py`'s `main()` (lines 241-258) does not use unittest auto-discovery -- it manually enumerates every test function in a `tests = [...]` list, and `run-all.py` runs each `test-*.py` as `python test-X.py`. Card 4's requirements add `test_slug_from_branch_retries_on_cold_daemon`, `test_slug_from_branch_exhausted_retry_propagates_wiki_startup_error`, and `test_task_data_retries_on_cold_daemon` but never instruct registering them in that `tests` list.
**Fix:** Add an explicit requirement bullet to Card 4: append the three new function names to the `tests` list in `test-marker.py`'s `main()`, or verify will report green while the new coverage silently never runs.

### [NIT] Other unguarded `_marker.slug_from_branch`/`task_data` call sites remain
**Location:** Batch 2 / Batch Scope
**Issue:** `millpy-abandon.py`, `millpy-color.py`, `millpy-cleanup.py`, `millpy-merge-in-subagent.py`, and `_review_common.load_task_title` (used by `_review_discussion.py:prepare()`, i.e. Batch 1's own dispatch path) all call `_marker.slug_from_branch`/`task_data` with only `except _marker.MarkerError`, so an exhausted-retry `WikiStartupError` still surfaces as a raw traceback there. Card 2's retry helper mitigates most cold-daemon hits for these callers too (transparently, before any exception reaches them), but the rare exhausted-retry case is still unguarded outside the two CLIs this batch touches.
**Fix:** Optional -- note as a follow-up/acknowledged gap; no plan change required if intentionally scoped to #579's reported call sites (millpy-implement.py/millpy-fix.py), consistent with the round-1 narrowing decision already recorded.

## Verdict

REQUEST_CHANGES
Card 4 adds three test-marker.py functions without registering them in main()'s `tests` list, so they would never run.
MILL_REVIEW_END
