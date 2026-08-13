MILL_REVIEW_BEGIN
# Review: mill-spawn, millpy-implement, _cleanliness, discussion-review: small bugs and inconsistencies

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5-class (self-assessed; harness metadata reports claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-13
```

## Findings

### [BLOCKING:scope] handoff.md's dirty-tree re-check omitted from #818 consumer list
**Section:** Decisions > cleanliness-unresolvable-parent-diff (#818); Technical context.
**Issue:** `handoff.md`'s Terminal cleanliness gate calls `_cleanliness.compute_terminal_dirt` twice — the initial check (`handoff.md:50`, the only call quoted in the discussion) and a post-self-resolve-commit re-check (`handoff.md:55`: "Re-run `_cleanliness.compute_terminal_dirt(...)`", branched on "If it is STILL non-empty..."). Both are the same binary-branch truthiness pattern the discussion explicitly warns about (`None` and `[]` both falsy), but only the first is named as needing the new `is None` branch.
**Fix:** Name both call sites explicitly in the #818 Decision/Technical-context text so the plan writer adds the `is None` escalation to the re-check at line 55 too, not just the initial check.

## Verdict

REQUEST_CHANGES
One BLOCKING gap: #818's handoff.md consumer list misses the gate's second (re-check) call site.
MILL_REVIEW_END
