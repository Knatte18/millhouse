MILL_REVIEW_BEGIN
# Review: mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-09
```

## Findings

### [GAP] status_path-absent scenario is not exclusively gated by require_pr_to_base
**Section:** Decisions / `mill-merge-status-absent-fallback` (#782)
**Issue:** The rationale claims the status_path-absent case is "only reachable via `require_pr_to_base: true`," which is why `cfg.git.base_branch` is treated as the *actual* parent, not an approximation. But `mill-merge/SKILL.md` Step 4 (`git -C <worktree> rm -r <task_dir>`, deleting status.md) runs *before* Step 5's own branch-protection auto-PR fallback, which later calls `_status.append_phase(status_path, "pr-pending", ...)` on the now-deleted file — `_status.append_phase` (`_status.py` line 456, `status_path.read_text(...)`) requires the file to exist and would raise. This fallback path is triggered purely by a rejected push, independent of `require_pr_to_base`, and the same Step 5 text documents parent != base_branch as a real, anticipated case ("parent is `develop`, base is `main`", line ~288). If this crash leaves the child branch pushed with task_dir already gone (sub-step 5 push precedes sub-step 6's failing append), a later mill-merge re-entry hits the exact status_path-absent case this decision is fixing, but without `require_pr_to_base: true` — where `base_branch` can be the wrong parent in a stacked-branch repo.
**Fix:** Confirm whether this Step-5-fallback crash path is actually reachable/persistent (vs. rolled back), and if so, either scope the Entry Step 4 fix to only trust `base_branch` when `require_pr_to_base` is confirmed true for this task, or resolve the true parent from the wiki task record instead of assuming `base_branch == parent_branch`.

## Verdict

GAPS_FOUND
One gap: base_branch-fallback rationale for #782 doesn't hold under mill-merge's own non-PR-mode branch-protection auto-PR path.
MILL_REVIEW_END
