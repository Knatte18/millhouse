# Review: 16 (A) — Autonomous bug-fix pipeline (mill-autofix)

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: task/discussion.md
date: 2026-05-07
```

## Findings

### [GAP] Post-merge success detection contradicts itself
**Section:** Technical context (`_status.py`) / Q&A log
**Issue:** `_status.py` entry labels `complete` as "not expected in autofix flow," yet the Q&A states mill-autofix detects merge failure by `phase != complete`; after a successful mill-merge the task branch is deleted and `task/status.md` is unreachable.
**Fix:** Clarify step j explicitly: success = mill-merge returned normally + current branch == parent_branch (squash SHA extraction is the positive signal); PR-path case = still on task branch, read `task/status.md` for `phase: pr-pending` before branch deletion; drop the contradictory `phase != complete` language.

### [GAP] Mill-merge in-place invocation is undocumented
**Section:** Technical context (mill-merge), Scope (In)
**Issue:** Mill-merge is documented as "Runs from the child worktree," but mill-autofix invokes it from the main worktree (`wts/millhouse/`) on the task branch; "in-place mode auto-detected" is undefined, and mill-merge SKILL.md changes are absent from scope.
**Fix:** Either confirm that mill-merge already handles this case and document the trigger condition, or add mill-merge SKILL.md to scope describing what "in-place mode" means — particularly for the worktree-removal and portal-cleanup steps that assume a dedicated `wts/<slug>/` exists.

## Verdict

GAPS_FOUND
Two gaps: post-merge detection is contradictory, and mill-merge in-place invocation is underdocumented.