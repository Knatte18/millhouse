MILL_REVIEW_BEGIN
# Review: Ask the parent session when stuck (parent_thread)

```yaml
duration_s: 314.4
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-25
```

## Findings

### [BLOCKING:design] one-escalation-per-site omits go-handoff-gate's granularity
**Section:** `one-escalation-per-site` **Issue:** the granularity list ("once per batch in mill-go, once per review loop in mill-plan/mill-start/holistic review, once per run in mill-quick") covers go-batch, plan-cap, start-cap, go-holistic-cap, and quick-gate, but never states one for `go-handoff-gate` — which itself spans two distinct gates (the "unfixed nits" halt and the done-gate-after-fixer halt) inside one Phase: Handoff run. **Fix:** state whether the budget is one escalation per handoff run (shared across both gates) or one per gate, so a run that clears unfixed-nits via `retry` and later hits the done-gate failure has a defined answer.

## Verdict

REQUEST_CHANGES
one-escalation-per-site leaves go-handoff-gate's escalation budget granularity undecided.
MILL_REVIEW_END
