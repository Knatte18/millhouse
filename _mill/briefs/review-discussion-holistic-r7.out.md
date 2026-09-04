MILL_REVIEW_BEGIN
# Review: mill-go: concurrency, silently-ignored fields, and bookkeeping bugs in execution/handoff

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [NIT:consistency] `_check_card_numbering` line-range citation excludes function tail
**Section:** Scope #906 / Technical context (helper reuse bullet) **Issue:** Both cite `_check_card_numbering` as `lines 908-962`; the function actually spans 908-974 — the omitted 957-974 is the cross-batch-uniqueness block that produces the very `errors` list the discussion's argument turns on. **Fix:** Correct the citation to `908-974` (verified against `plugins/mill/scripts/_plan_validate.py`); the underlying design conclusion (helper unusable pre-write) is unaffected.

## Verdict

APPROVE
All Decisions/Scope claims spot-checked against source (line numbers, signatures, key names) verify exactly; only a trivial citation-range nit found.
MILL_REVIEW_END
