MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution

```yaml
duration_s: 208.0
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact minor version not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [BLOCKING:design] 817 liveness check uses an unreliable dead-branch signal
**Section:** Decisions / 817-dead-parent-detection. **Issue:** the check verifies `parent_branch` via `git branch -a` / `git worktree list`, but `git branch -a` lists local remote-tracking refs (`refs/remotes/origin/*`) which are NOT pruned by `git push origin --delete` — confirmed `millpy-cleanup.py:_delete_remote_branch` (lines 426-450, called at 528-529 and 583-586) does exactly `git push origin --delete <branch>` with no accompanying `--prune` anywhere in mill-cleanup, so a torn-down parent's stale `origin/<parent_branch>` ref survives locally and `git branch -a` would report it as still alive — a false negative in precisely the "merged and torn down" scenario #817 exists to catch.
**Fix:** use `git ls-remote --exit-code origin <parent_branch>` instead (or in addition, with a `git fetch --prune` beforehand) — this exact pattern is already established in this codebase for the same class of check (`mill-resume/SKILL.md:222`, `git-pr/SKILL.md:93`); the Decision should name it explicitly rather than `git branch -a`.

## Verdict

REQUEST_CHANGES
The 817 liveness-check mechanism as specified will false-negative on its primary target scenario.
MILL_REVIEW_END
