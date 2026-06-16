MILL_REVIEW_BEGIN
# Review: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-16
```

## Findings

### [BLOCKING] Card 7 threading patch target is wrong binding
**Location:** Batch 3 / Card 7 (test-millpy-implement.py threading case)
**Issue:** `millpy-implement.py` does `from _implementer_common import ... finalize_from_output` (line 36), so it holds its own module binding; patching `_implementer_common.finalize_from_output` as the card instructs will NOT intercept the `--stage finalize` call and the assertion on `verify_cmd` will fire against the real (unpatched) function or never run.
**Fix:** Patch `millpy_implement.finalize_from_output` (the name imported into the CLI module), matching the file's existing `_p(millpy_implement.<attr>, ...)` setUp convention.

### [NIT] Card 5 gate-on-parsed-emit could re-run verify on a parsed stuck report
**Location:** Batch 3 / Card 5 (`_forward_output` parsed-success emit)
**Issue:** The parsed-emit path (line 250) prints the parsed dict whether its `status` is `success` OR `stuck`; "before the parsed-success emit" is correct only if gated on `parsed.get("status") == "success"`, else a self-reported `stuck` would needlessly trigger verify.
**Fix:** Have card 5 state explicitly that the gate call is guarded by `parsed.get("status") == "success"` at the parsed-emit point.

### [NIT] Card 3 should state divergence-warning still fires only on non-zero heading_count
**Location:** Batch 3->actually Batch 1 / Card 3 (test case b)
**Issue:** Card 2 returns early when `heading_count == 0`; card 3 case (b) uses two `### [GAP]` headings (count 2) so the warning still fires — correct — but the card does not call out that case (a)'s zero-heading early-return is the load-bearing assertion, risking a test that only checks the count and not warning suppression.
**Fix:** Card 3 already specifies stderr capture; add one word making the "NO warning emitted" assertion in case (a) explicit (it is implied but not asserted in prose).

## Verdict

REQUEST_CHANGES
One blocking test-patch-target error in card 7; two minor specification tightenings.
MILL_REVIEW_END
