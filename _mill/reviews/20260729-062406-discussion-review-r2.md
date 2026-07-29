MILL_REVIEW_BEGIN
# Review: mill-merge misjudges worktree topology and mishandles Step 5 squash-restore checkout

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Out-of-scope caller inventory for `prompt_stale_worktree` is wrong
**Section:** Scope › Out
**Issue:** Scope says `prompt_stale_worktree`'s callers are "millpy-cleanup.py / `_paths.resolve_active_worktree`," but `_paths.resolve_active_worktree` (verified in `_paths.py:378-450`) never calls `prompt_stale_worktree` — it only calls `_inplace.is_inplace` (line 433). The actual third caller is `mill-merge/SKILL.md`'s own Entry Step 1 "Stale-worktree edge" block (`SKILL.md:23`), which documents an inline call to `_inplace.prompt_stale_worktree(slug, worktree_path)` and is not mentioned anywhere in the Out section.
**Fix:** Correct the Out-section caller list to `millpy-cleanup.py` and `mill-merge/SKILL.md`'s own stale-worktree-edge block (drop the incorrect `_paths.resolve_active_worktree` reference), same way the r1 gap corrected `is_inplace`'s caller inventory.

## Verdict

GAPS_FOUND
One factual caller-inventory error in Scope's Out section, mirroring the class of gap already fixed once for is_inplace.
MILL_REVIEW_END
