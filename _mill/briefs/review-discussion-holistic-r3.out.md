MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (best-effort self-assessment)
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [BLOCKING:design] 817 chain-walk hardcodes `_mill/status.md`, ignoring documented `task/` legacy layout
**Section:** Decisions/817-dead-parent-detection **Issue:** The chain-walk reads `git show archive/<slug>~1:_mill/status.md` unconditionally, but `_paths.resolve_task_path` (repo-wide, hard-constraint helper per CLAUDE.md "all path resolution through `_paths.py`") and `mill-merge/SKILL.md`'s own "Board discipline" section both document `task/` as a still-live legacy layout ("`_mill/` for current worktrees, `task/` for legacy"). An archive tag pre-dating the `_mill/` rename would have `task/status.md` at `~1`, not `_mill/status.md` — the hardcoded read would silently misclassify that hop as "chain legitimately ends" (fallback trigger b in the same Decision) instead of correctly resolving the ancestor's parent. **Fix:** State explicitly whether legacy `task/`-layout archives are in scope for the chain-walk; if so, try both paths (or route through `_paths.py`-equivalent compat logic) before treating a missing file as chain-end.

### [BLOCKING:design] Testing plan omits the FF-only-merge-failure halt path
**Section:** Testing / 824-parent-fast-forward **Issue:** The 824-parent-fast-forward Decision's entire rationale for choosing FF-only merge over `reset --hard` is safety when the parent worktree has local-only commits not in origin (halt loudly instead of destroying them) — yet the Testing section's 824 bullet only covers (a) origin-advanced-past-local-ref success and (b) generic Step 1-5 rollback; it never asserts the new FF-only-failure halt itself (local commits present → halt, no mutation, rollback-exempt). **Fix:** Add a third 824 integration-test case: parent worktree has a local-only commit not in origin, assert Step 5 halts before `merge --squash`, nothing is mutated, and the halt is exempt from the Steps 1-5 rollback.

## Verdict

REQUEST_CHANGES
Two BLOCKING gaps: 817's chain-walk path assumption and 824's missing FF-failure test coverage.
MILL_REVIEW_END
