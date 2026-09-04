MILL_REVIEW_BEGIN
# Review: millpy-implement/bg: Windows baseline-worktree teardown (WinError 145) and stale liveness reporting

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] mill-cleanup safety-net detection criterion inverted vs. actual leak
**Section:** `### teardown-safety-net` Decision + Testing ("mill-cleanup sweep extension")
**Issue:** The decision detects orphaned `.scratch/verify-baseline-*` dirs via "no longer registered in `git worktree list`." Verified against `_worktree.remove_safe` (`plugins/mill/scripts/_worktree.py`): on the exact failure this decision targets (rmtree fallback exhausts retries → `WorktreeLockedError` raised), the raise happens *inside* the try/except and unwinds past the `git worktree prune` call at the end of the function — so `prune` never runs and the leaked worktree stays **registered** in `git worktree list`, not de-registered. `millpy-cleanup.py` also never calls `worktree prune` itself anywhere in its own flow (confirmed by reading the full file). The stated criterion therefore skips exactly the directories the safety net exists to reclaim; the Testing section's own fixture ("orphaned dir not in `git worktree list` output") encodes the same false premise.
**Fix:** Resolve the detection heuristic before planning — e.g. age/mtime-based, or re-attempting `git worktree remove`/`prune` as part of the sweep and only then checking registration, distinguishing a stale-but-registered leak from a live in-progress baseline computation.

## Verdict

REQUEST_CHANGES
Safety-net decision's detection method contradicts the verified failure mode it targets.
MILL_REVIEW_END
