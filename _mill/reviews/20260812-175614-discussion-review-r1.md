MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution

```yaml
duration_s: 163.0
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewer_self_id: Claude Sonnet 5
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [BLOCKING:design] 824 fast-forward mechanism: reset vs FF-merge not equivalent
**Section:** 824-parent-fast-forward Decision **Issue:** presents "fetch + reset" and "fetch + FF-only merge" as interchangeable implementations, but `git reset --hard origin/<parent>` silently discards any local-only commits on the parent's branch (destructive), while an FF-only merge fails loudly instead of discarding — no criterion picks between them. **Fix:** decide one mechanism explicitly; if reset is chosen, justify silently discarding un-pushed parent commits given the sibling 824-rollback-ref decision treats exactly this class of silent destruction as the bug being fixed.

### [BLOCKING:design] 819 gate condition rests on an undefined "suspect" is_inplace() result
**Section:** 819-stale-worktree-gate Decision **Issue:** the narrowed gate cites "an `_inplace.is_inplace()` result that's itself suspect" as a trigger condition; verified `_inplace.is_inplace()` (`_inplace.py`) is a deterministic git-topology boolean comparison with no error/uncertainty return and no documented notion of a "suspect" result — nothing in the codebase defines what would make it suspect. **Fix:** replace with a concrete, checkable condition (e.g. derive the gate purely from the already-cited `git worktree list --porcelain` staleness/absence/branch-mismatch check) or define "suspect" operationally.

### [BLOCKING:design] 817 chain-walk has no stated data source for a torn-down task's own parent
**Section:** 817-dead-parent-detection Decision **Issue:** "walk that task's own former parent" implies reading the resolved slug's `parent:` field, but verified `mill-merge/SKILL.md` Step 4 removes `_mill/status.md` in the cleanup commit, and Step 6 tags exactly that post-cleanup tip as `archive/<slug>` — so the tag's tree never contains status.md. Verified `wiki/_client.get_task()` also returns no `parent` field. No documented source exists for the chain-walk step as written. **Fix:** specify the actual read path (e.g. `git show archive/<slug>~1:_mill/status.md`, reading the pre-cleanup parent commit) or state the walk is limited to one hop / infeasible beyond it.

### [NIT:consistency] 817 "if none" fallback wording ambiguous against Testing section
**Section:** 817-dead-parent-detection Decision vs Testing **Issue:** the Decision's parenthetical "(or fall back to `cfg.git.base_branch` if none)" conflates two distinct triggers — "chain ends, no further former parent" vs "no `archive/<slug>` tag found at all" — only the Testing section's case (b) clarifies the no-tag case falls straight to `base_branch`. **Fix:** state both fallback triggers explicitly in the Decision itself, not only in Testing.

## Verdict

REQUEST_CHANGES
Three design gaps (824 ff-mechanism ambiguity, 819 undefined "suspect" trigger, 817 unspecified chain-walk data source) need resolution first.
MILL_REVIEW_END
