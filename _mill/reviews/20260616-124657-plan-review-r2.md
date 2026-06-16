MILL_REVIEW_BEGIN
# Review: Fix nested mill layout paths, whole-repo formatter drift, and stacked-branch PR cleanup — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-16
```

## Findings

### [NIT] Card 10 mis-states that task_dir is out of scope at 2b
**Location:** Batch 3 / Card 10, edit (3)
**Issue:** Card claims "`task_dir` ... neither is in scope at 2b today", but mill-go Path Setup (step 4.5, line 47) already assigns `task_dir = status_path.parent` globally, so it is in scope; only `parent_branch` genuinely needs deriving at 2b.
**Fix:** Drop the re-derivation of `task_dir` in 2b and reuse the existing Path-Setup variable; derive only `parent_branch` there.

### [NIT] worktree arg ambiguity for the drift-revert call
**Location:** Batch 3 / Card 10, edit (3)
**Issue:** `revert_out_of_scope_drift(<worktree>, task_dir, ...)` must receive the git checkout root (so `task_dir.relative_to(worktree)` and `git checkout` work), but mill-go's `worktree_root` is the hub (resolve_active_hub), which differs from the checkout root in a nested layout; the card leaves `<worktree>` as an unbound placeholder.
**Fix:** State explicitly that the first arg is the git checkout root (resolve_git_root / the existing `<worktree>` used by `compute_new_dirt`), not `worktree_root`.

### [NIT] Card 1 briefs path applies only to the prepare stage
**Location:** Batch 1 / Card 1
**Issue:** The discussion CLI builds `briefs_dir` from `git_root` only inside the `--stage prepare` branch (line 96); the card's wording reads as if it is a single top-level assignment.
**Fix:** Cosmetic — clarify the edit targets the prepare-stage `resolve_task_path(git_root, ...)` line; no behavioral change needed.

## Verdict

APPROVE
Source-accurate, complete cards, valid DAG and numbering; findings are cosmetic only.
MILL_REVIEW_END
