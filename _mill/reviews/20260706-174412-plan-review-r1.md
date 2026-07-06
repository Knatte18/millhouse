MILL_REVIEW_BEGIN
# Review: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-06
```

## Findings

### [BLOCKING] Card 5 omits the 6 CV-* direct compute_scope_violations calls
**Location:** Batch 1 / Card 5
**Issue:** Card 1 makes `compute_scope_violations` require two args, but Card 5 only updates the 9 CESV cases; the 6 existing CV-1..CV-6 cases (test-cleanliness.py lines 179, 191, 203, 215, 230, 245) still call `compute_scope_violations(Path(tmp))` with one arg and will raise `TypeError`, failing batch 1's own verify (`test-cleanliness.py`).
**Fix:** Add to Card 5 a requirement to update all 6 CV-* cases to pass `(Path(tmp), Path(tmp))`, assertions unchanged.

### [NIT] Card 23 requires unstated signature/wiring changes
**Location:** Batch 6 / Card 23
**Issue:** `_check_verify_full_suite(batch_files)` has no `project_root` param, yet Card 23 tells both checks to call `parse_verify_field(parsed, project_root, project_root)`; neither existing check receives the overview path, yet Card 23 tells them to also iterate the overview's `verify:`. The card names neither the signature additions nor the `run()` call-site updates (lines 1494-1495) needed to make this implementable.
**Fix:** State that both functions gain `project_root`/`overview_path` params and that `run()`'s two call sites are updated to pass them.

### [NIT] Card 13/16 threading is under-specified vs. actual call counts
**Location:** Batch 4 / Cards 13, 16
**Issue:** Card 13 says thread the new overrides into "their internal `_run_verify_gates(...)` call," but `_forward_output` has four such call sites (952, 1139, 1233, 1323) and `finalize_from_output` threads via `_forward_output`, not `_run_verify_gates` directly. Card 16 requires deriving `cwd_override_relative` inside `_run_baseline_stage`, which currently lacks a `module_wide_cwd_override` param and whose call site (line 318) is not mentioned.
**Fix:** Name all four `_forward_output` gate sites and the `_run_baseline_stage` param + line-318 call update.

### [NIT] Cards 23 and 24 both emit malformed-cwd findings
**Location:** Batch 6 / Cards 23, 24
**Issue:** Card 23 has the two existing checks emit a `verify-malformed-cwd` finding on `ValueError`, and Card 24 adds a dedicated `_check_verify_malformed_cwd` doing the same, so one malformed mapping surfaces as duplicate findings.
**Fix:** Have the Card 23 checks `continue` on `ValueError` and let Card 24's dedicated check be the sole reporter.

## Verdict

REQUEST_CHANGES
One BLOCKING test-completeness gap in Card 5; remaining wiring/spec gaps are NITs.
MILL_REVIEW_END