MILL_REVIEW_BEGIN
# Review: Improve diagnosability of plan-validate errors and finalize verify-replay failures

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] Empty extracted-signature set is vacuously "subset of baseline"
**Section:** `gap2-subset-diff-semantics` / `gap2-failure-signature-extraction`
**Issue:** `_extract_failure_signatures` returns `[]` for ANY non-zero-exit output containing no recognized FAIL-marker line (build/compile errors, crashes, linter failures, unrecognized test runners) — an empty set is mathematically a subset of every baseline set (including an empty one), so the stated subset-check would silently waive these failures as "passed," even a genuinely new regression the batch itself introduced, as long as its failure output doesn't happen to match the fixed marker list.
**Fix:** Define an explicit non-vacuous rule, e.g. "a non-zero exit with zero extracted signatures is never eligible for baseline waiver and always blocks" — distinguish this case from a truly clean (`rc==0`) baseline/replay, which today both collapse to the same `[]` representation.

### [GAP] `_run_verify_gate`'s exception-path stuck dict has no `signatures` key
**Section:** `gap2-signatures-field-on-stuck-dict`
**Issue:** `_run_verify_gate` (`_implementer_common.py:810-817`) returns a `stuck_type: "verify"` dict from its `except Exception` branch (missing binary, `FileNotFoundError`, etc.) with only `status`/`stuck_type`/`reason` — no subprocess `output` exists there to extract signatures from. The decision text ("gains a `signatures` field ... when `stuck_type == 'verify'`") doesn't distinguish this path from the normal non-zero-exit path, so `_run_verify_gates`' new subset-diff (`batch_result["signatures"]`) either KeyErrors or (if defaulted to `[]`) falls into the same vacuous-waiver bug as the first finding — silently passing infrastructure failures like a missing test binary.
**Fix:** State explicitly that the exception path either omits `signatures` and is unconditionally excluded from baseline-diff eligibility, or sets `signatures` to a sentinel distinct from "verify passed"/"no markers matched."

## Verdict

GAPS_FOUND
Empty/absent signature sets are ambiguous between "clean" and "unmatched failure," risking silent regression waivers.
MILL_REVIEW_END
