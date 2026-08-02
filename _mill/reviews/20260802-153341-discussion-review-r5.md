MILL_REVIEW_BEGIN
# Review: Improve diagnosability of plan-validate errors and finalize verify-replay failures

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; exact point version not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] `_run_baseline_stage`'s early returns bypass per-batch computation
**Section:** Decisions/gap2-compute-eagerly-before-batch-1; Technical context (`millpy-implement.py:78`)
**Issue:** Confirmed in source (`millpy-implement.py:114-124, 126-129`): `_run_baseline_stage` returns 0 immediately when `module_wide_verify_cmd is None` (an explicitly normal, documented config per the comment at line 354 — "A null or absent `verify:` passes None, which makes the module-wide gate a no-op") and again when the module baseline is already cached — both checks execute BEFORE any batch-related work. The discussion's plan to "extend" this same function for per-batch enumeration never addresses these two early-exit points; a naive extension (new logic appended after existing logic, as "extend" implies) means per-batch baselines are NEVER computed for any task lacking a module-wide verify command, and are never backfilled on a resumed run if a prior invocation's module-wide baseline already succeeded while per-batch computation crashed partway through — directly undermining the `gap2-per-batch-baseline-idempotency` Decision's own stated guarantee ("must still fill in any [batches] that hadn't been reached yet").
**Fix:** Add an explicit Decision/Technical-context note that `_run_baseline_stage` must restructure its control flow so per-batch enumeration/computation runs independently of the module-wide-specific early returns (no-module-wide-verify-configured, and module-baseline-already-cached), gated only by the per-batch `verify_baseline_failures`-already-set check.

## Verdict

GAPS_FOUND
`_run_baseline_stage`'s existing early-return gates would silently disable per-batch baselines for common configs.
MILL_REVIEW_END
