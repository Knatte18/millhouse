MILL_REVIEW_BEGIN
# Review: mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-25
```

## Findings

### [NIT] Prefix-strip branch-slug logic duplicated across two batches
**Location:** `plugins/mill/scripts/_review_common.py:322-323` (`find_active_slug`) and `plugins/mill/scripts/_paths.py:426-427` (`resolve_active_worktree`'s `skip_slug_validation` branch)
**Issue:** Both sites independently compute `prefix = cfg.get("spawn", {}).get("branch_prefix", "")` then `branch.removeprefix(prefix) if branch.startswith(prefix) else None` — identical two-line logic, introduced by batch 2 (Card 3) and batch 3 (Card 6) respectively.
**Fix:** Not blocking given the trivial size and the two call sites' differing surrounding context (one needs `ReviewError`-flavored fallback, the other `ActiveWorktreeNotFound`), but a future pass could extract a tiny `_branch_slug(branch, prefix)` helper into `_pygit2_util.py` or `_paths.py` if a third caller appears.

## Verdict

APPROVE
Every batch's cards are fully realised, cross-batch contracts hold, and test coverage matches each card's requirements exactly.
MILL_REVIEW_END
