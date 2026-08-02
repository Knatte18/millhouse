MILL_REVIEW_BEGIN
# Review: Improve diagnosability of plan-validate errors and finalize verify-replay failures

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet 5)
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] Gap-1 repro mechanism doesn't match the confirmed code
**Section:** Problem (Gap 1) / Testing
**Issue:** `_check_context_completeness`'s loop calls `backtick_re.findall(line)` per individual line string with no state carried across iterations (`_plan_validate.py:1536-1537`); a genuinely split backtick pair leaves one dangling backtick per line, so `findall` matches nothing on either line -- it cannot "mis-pair" across lines to synthesize a bogus token as described.
**Fix:** Re-derive the actual #772 repro (e.g. a single line with an odd backtick count from an unrelated apostrophe/escape) before writing the regression test.

### [GAP] Shared signature-extraction helper may inherit the existing 20-line cap
**Section:** Decisions / gap2-failure-signature-extraction; Technical context (`_implementer_common.py:792-797`)
**Issue:** the cited inline code being lifted into the shared helper caps extracted lines at `[:20]` (built for a truncation excerpt, not correctness); if reused unmodified for baseline/finalize signature sets, failures past the 20th FAIL-marker line are silently absent from both sets, so a genuine new regression past that point can never be detected.
**Fix:** State explicitly whether the shared helper drops the cap, versus the truncation-excerpt call site keeping its own separate cap.

### [GAP] Unclear how the full failure-signature set reaches `_run_verify_gates`' subset-diff
**Section:** Technical context (`_implementer_common.py:690, 822`)
**Issue:** `_run_verify_gate` returns only `{status, stuck_type, reason}` (reason possibly truncated to a 2000-char tail); `_run_verify_gates` is named as the place that "performs the subset-diff," but it never sees raw subprocess output, only that dict.
**Fix:** Decide whether `_run_verify_gate`'s stuck dict gains a new `signatures` field, or the diff logic actually lives inside `_run_verify_gate` instead.

### [GAP] No idempotency contract for the multi-batch `--stage baseline` extension
**Section:** Decisions / gap2-compute-eagerly-before-batch-1
**Issue:** today's single `module_verify_baseline` cache is one scalar with a one-shot "already cached -> skip" check (`millpy-implement.py:126-129`); nothing says how re-invocation on a resumed run should treat a per-batch dict where some batches already have `verify_baseline_failures` set and others don't.
**Fix:** Specify per-batch cache-hit semantics (skip only already-computed batches vs. recompute-all).

### [GAP] `iter_batch_verifies`' stale-command filter silently excludes some batches from ever getting a baseline
**Section:** Decisions / gap2-compute-eagerly-before-batch-1; Technical context (`_plan_dag.py:499`)
**Issue:** a batch whose own `verify:` references a path a strictly-later batch deletes/moves is dropped from `iter_batch_verifies`' output ("reason 2"), so its baseline is never computed even though its own finalize still runs that verify command for real before the later deletion executes -- that batch permanently falls back to today's strict any-failure-blocks behavior.
**Fix:** Call out this coverage gap explicitly, or enumerate for baseline purposes independent of reason-2 suppression.

### [NOTE] Two Technical-context counts are off
**Section:** Decisions / gap1-line-field-not-line-number; Technical context (test file)
**Issue:** `_parse_cards` actually has 6 other call sites (758, 850, 884, 1526, 1753, 2585), not 5 (1753, in `_check_requirements_quote_indent_drift`, is missing); `test-plan-validate.py` has 17 `test_check_context_completeness_*` functions, not 14.
**Fix:** Correct the counts (doesn't change either decision's conclusion).

### [NOTE] New batch field's type hint not updated
**Section:** Technical context (`_status.py` `_BATCH_ALLOWED_KEYS`/`set_batch_field`)
**Issue:** `set_batch_field`/`set_batch_fields` are typed `value: str | int | None`; the new `verify_baseline_failures` field is a `list[str]`, which works at runtime but leaves the signature inaccurate.
**Fix:** Widen the type hint when the field is added.

## Verdict

GAPS_FOUND
Gap-1's stated repro mechanism looks unreproducible per source; gap-2 has unresolved plumbing/coverage/idempotency gaps.
MILL_REVIEW_END
