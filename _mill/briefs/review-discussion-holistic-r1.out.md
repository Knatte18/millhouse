MILL_REVIEW_BEGIN
# Review: millpy-implement finalize/resume fixes and the red integration suites

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-26
```

## Findings

### [BLOCKING:design] resume-brief-dirty rests on an unverified root cause
**Section:** Decisions / resume-brief-dirty **Issue:** `_in_scope_dirty_stuck` already excludes `line.startswith("_mill/briefs/")` (`_implementer_common.py` line 472, and its docstring cites #885), so the decision's premise that the current predicate misses the reported paths is unproven, and the decision itself defers the real fix to "whatever the reproduction shows". **Fix:** State the actual mechanism before planning (for example which path form `git diff --name-only` and `status_porcelain` produce for the reported brief and `.out.md`, or whether the task dir is not at repo root), or make the decision explicitly a reproduce-then-decide task with a defined fallback.

### [NIT:scope] Fallback for resume-brief-dirty leaves prepare-side option open
**Section:** resume-brief-dirty **Issue:** If reproduction shows the predicate is correct, the "remaining fix" could land on prepare or on the dirty-gate input, contradicting the "finalize side, not prepare side" decision. **Fix:** Say which side is authoritative if the reproduction contradicts the premise.

### [NIT:scope] Threading list is descriptive, not exhaustive
**Section:** commit-none-recount **Issue:** "the four `_batch_completeness_stuck` call sites" is a snapshot count. **Fix:** Name the rule (every caller of `_cards_incomplete_reason` and `_batch_completeness_stuck` gets the set) and leave counting to the build.

## Verdict

REQUEST_CHANGES
The #1162 finalize-side fix targets a predicate that already excludes `_mill/briefs/`; the root cause needs stating.
MILL_REVIEW_END
