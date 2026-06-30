I have verified the key claims. The discussion accurately describes `_apply_pr_reap_record` (line 573, query with `cwd=hub_root`, JSON fields `state,mergeCommit,number`, tolerant of non-zero exit), the mill-merge SKILL.md phase gate (Step 5) and `## PR-path re-entry` section, and the `_archive_tag.create_or_resolve(worktree, slug, child_branch)` call site. I found one internal contradiction and a related parity tension.

MILL_REVIEW_BEGIN
# Review: Handle pre-closed and pre-merged PRs gracefully in mill-merge

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-30
```

## Findings

### [GAP] Query form contradicts precedence decision
**Section:** Scope (helper) vs Decisions/normalized-state-precedence
**Issue:** Scope describes `_pr_state.py` as wrapping the existing `gh ... --state all --json ... --jq '.[0]'` query, but normalized-state-precedence explicitly rejects trusting `--jq '.[0]'` ordering and requires fetching all PRs to apply MERGED>OPEN>CLOSED — the helper cannot do both.
**Fix:** State definitively that `_pr_state.py` drops `--jq '.[0]'`, returns the full array, and computes precedence in Python; remove the `.[0]` form from the Scope description.

### [GAP] "Identical behavior" for cleanup conflicts with precedence
**Section:** Technical context (_apply_pr_reap_record) vs normalized-state-precedence
**Issue:** Refactoring `_apply_pr_reap_record` onto a precedence-based helper changes its multi-PR behavior — today it acts on the most-recent PR (`.[0]`), so an older MERGED behind a recent CLOSED would now finalize where it previously skipped; this is not "observable behavior identical."
**Fix:** Decide and record whether cleanup adopts the new precedence (behavior intentionally improves) or must preserve `.[0]` semantics, so the refactor's contract is unambiguous.

### [NOTE] Archive-tag target differs between the two MERGED routes
**Section:** Decisions/merged-remote-cleanup-only vs Technical context
**Issue:** The mill-merge MERGED route tags the local cleanup-commit tip via `create_or_resolve`, while `_apply_pr_reap_record` tags the remote merge (FETCH_HEAD/merge SHA); the discussion unifies only the query, not the tag target.
**Fix:** Note that the tag-target divergence is intentional so the plan writer does not "unify" the teardown too.

### [NOTE] MERGED route leaves local parent behind remote
**Section:** Decisions/merged-remote-cleanup-only
**Issue:** Skipping Steps 1–2 and 5 means the local parent branch is never synced with the remote squash; it stays behind remote until the next pull (benign but unstated).
**Fix:** State that the local parent is intentionally not fast-forwarded in cleanup-only mode.

## Verdict

GAPS_FOUND
Internal contradiction on the PR-query form (`.[0]` vs precedence) must be resolved before planning.
MILL_REVIEW_END