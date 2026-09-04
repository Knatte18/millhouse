MILL_REVIEW_BEGIN
# Review: millpy-implement/bg: Windows baseline-worktree teardown (WinError 145) and stale liveness reporting — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (Sonnet 5, per system framing)
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [BLOCKING:scope] Card 7 Requirements call `_worktree.remove_safe` but `_worktree.py` is not in Context
**Location:** batch 03 (`04-baseline-undercount-corroboration.md`), Card 7. **Issue:** `_corroborate_batch_failure`'s Requirements mandate `import _worktree` and a fully-specified `_worktree.remove_safe(tmp_path, cwd=effective_git_root, junctions_cfg={})` call inside `_implementer_common.py` (a module with no prior `_worktree` dependency), but Card 7's `Context:` list has only `plugins/mill/scripts/_verify_baseline.py`; `_worktree.py` appears in neither `Context:` nor `Edits:`. **Fix:** Add `plugins/mill/scripts/_worktree.py` to Card 7's `Context:` list.

## Verdict
REQUEST_CHANGES
Card 7 introduces a new `_worktree.remove_safe` dependency without listing `_worktree.py` in its Context.
MILL_REVIEW_END
