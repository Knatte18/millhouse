MILL_REVIEW_BEGIN
# Review: Improve diagnosability of plan-validate errors and finalize verify-replay failures

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] `--stage baseline`'s new JSON output shape left as an either/or
**Section:** Decision `gap2-baseline-stage-independent-of-module-wide-early-returns`
**Issue:** The new two-sub-step output contract is given as "e.g. `{"stage": "baseline", "module_wide": {...}, "per_batch": {...}}` or two separate printed JSON lines" — an unresolved alternative, not a decision.
**Fix:** Pick one concrete shape; `mill-go/SKILL.md`'s "0.5. Baseline pre-flight" parsing update (Technical context) depends on knowing the exact structure to parse.

### [GAP] No failure-isolation design for per-batch baseline computation errors
**Section:** Decisions `gap2-per-batch-baseline-idempotency` / `gap2-checkout-teardown-extraction`; Technical context `_run_baseline_stage`
**Issue:** `_run_baseline_stage` must never raise (existing module-wide path wraps `compute_baseline` in try/except and prints `{"result": "error", ...}` on failure). The new per-batch loop over N batches has no stated exception-isolation policy — if one batch's verify subprocess/checkout step raises, it's unspecified whether that aborts the whole invocation (silently losing the module-wide result and any not-yet-reached batches' baselines) or is caught per-batch so others still complete and persist.
**Fix:** State that each batch's computation is individually try/except-wrapped, leaving only that batch's `verify_baseline_failures` unset (fail-safe to strict) on error, without preventing the module-wide sub-step or sibling batches from completing.

## Verdict

GAPS_FOUND
Two design gaps: undecided baseline-stage JSON shape and missing per-batch computation failure-isolation policy.
MILL_REVIEW_END
