I have verified the discussion's claims against the source files. Key verifications:

- `_apply_pr_reap_record` exists at line 573 of `millpy-cleanup.py`, uses `gh pr list --head ... --json state,mergeCommit,number --jq '.[0]'` (line 586-590) with `cwd=hub_root` — matches the discussion.
- The MERGED-route tag-target fallback at line 635 reads `(merge_commit or {}).get("oid")`.
- `mill-merge` SKILL.md: `CHILD_BRANCH` captured at Step 3 (line 79); existing `## PR-path re-entry` table (line 258-267) shows the current `pr-pending` MERGED route "Skip Steps 1-5" (i.e. skips Step 4 cleanup commit), and CLOSED -> "orphaned -> /mill-abandon" — both as the discussion describes.

MILL_REVIEW_BEGIN
# Review: Handle pre-closed and pre-merged PRs gracefully in mill-merge

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-30
```

## Findings

### [NOTE] merge_commit shape left unspecified
**Section:** Decisions/normalized-state-precedence; Technical context
**Issue:** The normalized result lists `merge_commit` but does not say whether it is the raw gh object or just the `.oid` string; `_apply_pr_reap_record` (millpy-cleanup.py ~line 635) reads `(merge_commit or {}).get("oid")` for its tag-target fallback.
**Fix:** State that `_pr_state.py` preserves the `mergeCommit` object (or exposes `.oid`) so the cleanup refactor keeps its fetch-failure tag target.

### [NOTE] "generalizes pr-pending MERGED" undersells a behavior change
**Section:** Decisions/merged-remote-cleanup-only
**Issue:** Today's `pr-pending` MERGED route skips Steps 1-5 (so it skips Step 4 cleanup commit) and tags the un-cleaned local tip; the new route adds Step 4, so the tagged tip differs — this is a change to the pr-pending route, not a pure generalization.
**Fix:** Note explicitly that the existing SKILL.md `## PR-path re-entry` MERGED branch (line 264) must be rewritten to run Step 4, not assumed identical.

### [NOTE] CLOSED-proceeds collides with branch-protection fallback
**Section:** Decisions/closed-no-merge-proceeds; Scope (Out)
**Issue:** In a branch-protected repo, the CLOSED route's local squash push is rejected, re-triggering the Step 5 fallback that auto-creates a new PR — contradicting the user's close-without-merge intent.
**Fix:** Acknowledge this interaction (even if the fallback stays out of scope) so the plan writer does not treat CLOSED -> local-squash as always terminal.

## Verdict

APPROVE
Decisions are complete with rationale; only minor clarifications, no blocking gaps.
MILL_REVIEW_END