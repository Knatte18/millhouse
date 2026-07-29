MILL_REVIEW_BEGIN
# Review: mill-merge misjudges worktree topology and mishandles Step 5 squash-restore checkout

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [NOTE] Caller count drifts within is-inplace-topology-check decision
**Section:** Decisions › is-inplace-topology-check
**Issue:** The Decision bullet justifies keeping `slug`/`cfg` in the signature "for API compatibility with both existing call sites (`_paths.py:433`, `millpy-cleanup.py:434`)" — omitting `mill-merge/SKILL.md:21`, which the very next Rationale bullet correctly counts as a third call site relying on the same 3-arg signature.
**Fix:** Change "both existing call sites" to "all three existing call sites" (adding the SKILL.md:21 reference) so the Decision bullet matches the Rationale bullet's count.

## Verdict

APPROVE
Technical claims, line refs, and caller/test inventories all verified accurate against source; only a cosmetic count nit found.
MILL_REVIEW_END
