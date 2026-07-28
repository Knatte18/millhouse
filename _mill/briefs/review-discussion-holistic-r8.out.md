MILL_REVIEW_BEGIN
# Review: Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-28
```

## Findings

### [GAP] 5 more hardcoded-blocking_count-0 sites lack nit_count parity
**Section:** Decisions > nit-count-fix-mechanism; Technical context site enumeration
**Issue:** `_review_one_batch()`'s two `except LLMError` returns (`_review_plan.py:238-246`, `273-281`) and its outer `except ReviewError` return (`306-314`), plus `run()`'s holistic-block two `except LLMError` appends (`905-913`, `941-949`) — verified by direct read — each hardcode `"blocking_count": 0` with no `"nit_count"` key, and each reaches `reviews[]`/the returned `ReviewResult` (per-batch entries via `future.result()` + `reviews.append`, holistic entries via direct `reviews.append`). This is the identical schema-parity gap round-6 fixed for the single holistic outer-`except ReviewError` site (1014-1024), but these 5 sibling sites are absent from both the site enumeration and the Decisions, with no stated rationale for treating them differently.
**Fix:** Either extend the round-6 "add `nit_count: 0` for schema parity" treatment to all 5 of these sites too, or add an explicit Decisions note (mirroring the resume-disk-scan exclusion's rationale) explaining why LLM-call-level failures are excluded from the parity fix while the parse_verdict-failure site is not.

## Verdict

GAPS_FOUND
One unaddressed class of hardcoded-blocking_count-0 sites (5 of them) lacks the same nit_count schema-parity fix already applied to a sibling site.
MILL_REVIEW_END
