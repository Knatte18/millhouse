Now I have enough information to write the review.

# Review: 46 (A) — Home.md state machine + split mill-merge teardown into mill-cleanup

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-11
```

## Findings

### [GAP] Archive tag commit target unspecified in PR-reap
**Section:** Decisions / `pr-reap-teardown-sequence`
**Issue:** `apply_plan` is instructed to "create archive tag if absent" when PR state is `MERGED`, but the target commit is never specified. In the direct path, the tag points to `HEAD` of the parent branch immediately after `git push`. For a PR-merged squash, the commit only exists on the remote until after a `git pull`; `mergeCommit` from the `gh pr list` JSON is the natural target, but this requires fetching that SHA explicitly.
**Fix:** Specify that the archive tag should be created pointing to the `mergeCommit` SHA from the `gh pr list` JSON response, and that a `git fetch` of that SHA or `git pull origin parent_branch` may be required first.

### [GAP] Orphan detection not extended to new states
**Section:** Technical Context / `millpy-cleanup.py`
**Issue:** The `build_plan` orphan check (current line 176-180) only fires for `task.phase == "active"`. With the new states, a `[ready-to-merge]` or `[pr-pending]` task whose worktree was manually deleted has no worktree entry in `active_worktrees` and is silently ignored, leaving its Home.md marker permanently stuck with no cleanup path.
**Fix:** State whether `[ready-to-merge]` and `[pr-pending]` tasks with no active worktree should be reported in `to_report`, or explicitly document that this case is out of scope for this task.

## Verdict

GAPS_FOUND
Two implementation-blocking unspecified details around PR-reap archive tag target and orphan state handling.