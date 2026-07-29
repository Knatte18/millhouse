MILL_REVIEW_BEGIN
# Review: millpy-implement.py --stage baseline: WinError 3 snapshotting a transient/generated file on Windows

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Testing Scenario 3 contradicts Technical Context on test-worktree.py
**Section:** Testing (Scenario 3) vs. Technical Context
**Issue:** Testing Scenario 3 says "add a `test-worktree.py` or `test-junction.py` case asserting `remove_safe` itself completes" with a vanished entry, but Technical Context explicitly lists `test-worktree.py` among files that "benefit from this fix without any changes of their own." Scope's "In" bullet also names only `test-safe-rmtree.py` and `test-junction.py` as files to add coverage to. A plan writer could reasonably go either way on whether `test-worktree.py` needs a new case.
**Fix:** Resolve the contradiction explicitly — either drop the `test-worktree.py` option from Scenario 3 (coverage confined to the two Scope-named files, with `test-junction.py` covering the `strip_all_in_worktree`-level assertion) or add `test-worktree.py` to Scope's "In" bullet and Technical Context's "benefits without changes" list.

### [NOTE] "Both `_junction.remove` implementations" is imprecise
**Section:** Decisions — Guard placement rationale
**Issue:** The text "Both `_junction.remove` implementations already re-check `os.path.lexists`/idempotency at their own entry" implies two separate implementations of `remove`, but there is exactly one `_junction.remove` function (in `_junction.py`), called from both walks (`_safe_rmtree._walk_strip_reparse_points` and `_junction.py`'s own `_walk`).
**Fix:** Reword to "both walks' calls into the single `_junction.remove`" to avoid implying a second implementation exists.

## Verdict

GAPS_FOUND
Testing Scenario 3's `test-worktree.py` option contradicts Technical Context's explicit "no changes" claim for that file.
MILL_REVIEW_END
