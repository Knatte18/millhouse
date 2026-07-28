MILL_REVIEW_BEGIN
# Review: Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-28
```

## Findings

### [GAP] Combined check-1/check-2 failure reporting unspecified
**Section:** Decisions / merge-in-marker-verification (#713)
**Issue:** When `--files` lists multiple files and different files trip different checks in the same gate run (e.g. file A never staged fails check 1, file B staged-with-markers fails check 2), the "(check 2) or (check 1)" phrasing doesn't say whether the gate short-circuits on the first failing check — losing the other file's finding until a later retry — or runs both checks unconditionally and merges both reasons into one `reason` string.
**Fix:** State explicitly whether both checks always run with reasons concatenated, or the first failing check wins and reporting the other is deferred to a subsequent gate run; Testing's fixtures currently exercise each check shape only in isolation, never both simultaneously across different files in one `--files` list.

## Verdict

GAPS_FOUND
One narrow gap: combined-failure reporting behavior across the two #713 marker-verification checks is unspecified.
MILL_REVIEW_END
