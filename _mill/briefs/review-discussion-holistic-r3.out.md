MILL_REVIEW_BEGIN
# Review: mill-go: done-gate halt path and cleanliness-gate recovery are under-documented

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (Sonnet 5 per harness label)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:consistency] terminal-dirt gate has 3 halt call sites, decision counts 2
**Section:** Decision `builder-lock-release-all-handoff-halts` vs. `## Technical context` bullet 2.
**Issue:** The decision text says "terminal-dirt gate (both of its two halt messages)", but `handoff.md`'s terminal cleanliness gate actually has three separate `BLOCKED:` call sites — line 53 (initial `None` check), line 59 (re-check after self-resolve, same message text as line 53), and line 61 (still-non-empty). The Technical context bullet itself correctly cites all three (`~lines 53/59/61`), contradicting the Decision's own "two" count.
**Fix:** Reword the Decision to say lock-release/notify go before all three call sites (grouping 53+59 as sharing message text, but both still requiring the edit), so a plan writer implementing "two halt messages" doesn't skip the line-59 re-check halt.

## Verdict

REQUEST_CHANGES
Decision's own halt-site count for the terminal-dirt gate contradicts the Technical context's line citations.
MILL_REVIEW_END
