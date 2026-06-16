MILL_REVIEW_BEGIN
# Review: Fix nested mill layout paths, whole-repo formatter drift, and stacked-branch PR cleanup — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-16
```

## Findings

### [BLOCKING] Card 10 step-2b wiring needs parent_branch, not in scope/Context
**Location:** Batch 3 / Card 10
**Issue:** `revert_out_of_scope_drift(<worktree>, task_dir, parent_branch)` is called in the step-2b cleanliness gate, but in mill-go `parent_branch` is only resolved at Handoff (line 653 via `_parent_branch.resolve(status_path, ...)`); step 2b (line 241) has no `parent_branch`, and the card's Context lists only `_paths.py`/`_cleanliness.py`, not `_parent_branch`.
**Fix:** Add a requirement to derive `parent_branch = _parent_branch.resolve(status_path, interactive=False)` in step 2b, and add `plugins/mill/scripts/_parent_branch.py` to the card Context.

### [BLOCKING] Card 10 status-path target is wrong line / incomplete
**Location:** Batch 3 / Card 10 (edit 1)
**Issue:** The only `status_path = _paths.resolve_task_path(_paths.resolve_git_root(), '_mill/status.md')` literal (line 151) sits inside the per-batch cleanup inline `python -c` subprocess, where `worktree_root` is NOT in scope — contradicting the card's "matching the `worktree_root` already derived via `resolve_active_hub`." A separate `git_root / '_mill/reviews'` (line 516, holistic crash-recovery helper) is also git-root-anchored and breaks in a nested layout but is unmentioned.
**Fix:** Clarify the line-151 fix uses an in-snippet `resolve_hub_path()` (no `worktree_root` available there), and either extend Card 10 to also fix the line-516 `_mill/reviews` anchor or state explicitly why it is out of scope.

## Verdict

REQUEST_CHANGES
Card 10's mill-go drift-guard wiring underspecifies parent_branch sourcing and mistargets the status-path callsite.
MILL_REVIEW_END
