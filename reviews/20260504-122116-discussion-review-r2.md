# Review: review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: discussion.md
date: 2026-05-04
```

## Findings

### [NOTE] Partial mid-round state not specified for run logic
**Section:** `mid-round-resume-discover-round` decision + Testing
**Issue:** `detect_resume_round` is specified to return N for partial rounds (some batches at round N, others only at round N-1), but `_review_plan.run`'s assembly behavior for batches lacking a round-N file is not stated — re-fire via ThreadPoolExecutor or fall back to round N-1?
**Fix:** Add one sentence to the decision or gotchas stating whether batches without a round-N file are re-fired (partial ThreadPoolExecutor) or use their highest-available file; the integration test covers only the complete-set case.

### [NOTE] Rate-limit `result.is_error` marker strings not enumerated
**Section:** `llm-rate-limit-error-class` decision + Testing (`_scan_rate_limit`)
**Issue:** The `rate_limit_event` event-type path is fully specified, but the secondary detection path — `result` event with `is_error: true` AND "a rate-limit subtype/message marker (matched by substring against the known claude CLI markers)" — does not list the actual marker strings, requiring the plan writer to research the claude CLI output format to write correct fixtures.
**Fix:** Add a one-line list of the known marker substrings (e.g. `"rate_limit"` in `type` or message field) so the plan writer can write accurate test fixtures without external research.

## Verdict

APPROVE
Two NOTEs, no GAPs; round-1 gaps are all closed and source claims verified.