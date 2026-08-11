MILL_REVIEW_BEGIN
# Review: mill-merge-in --recompute-baseline crashes uncaught on absent status.md — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4-5 (self-assessed; environment reports "Sonnet 5" / claude-sonnet-5)
reviewed_file: plan/
date: 2026-08-11
```

## Findings

### [BLOCKING:consistency] Test-insertion location instruction contradicts itself
**Location:** Batch crash-fix, Card 1 (test file edit)
**Issue:** Requirements say to insert `test_20_recompute_baseline_missing_status_md` "immediately before the `class TestVerifyConflictMarkersGate` line (end of `TestMillpyMergeInSubagent`'s body)" — but in the actual file, `TestMillpyMergeInSubagent`'s body truly ends at line 846 (`test_2x_finalize_conflicts_missing_files_flag`), and a standalone module-level helper `def _git(args, cwd, check=True):` (lines 849-861) sits between that and `class TestVerifyConflictMarkersGate` (line 864). The two locations named in the same sentence are ~18 lines apart and not equivalent.
**Fix:** Disambiguate: state explicitly to insert directly after `test_2x_finalize_conflicts_missing_files_flag` (still inside `TestMillpyMergeInSubagent`'s indented body) and before the blank lines / `_git` helper, not merely "before the class line" — following the literal instruction would place the new method outside the class (after `_git`), breaking indentation/`self` semantics.

### [NIT:consistency] Docstring's enumerated failure-path list not updated
**Location:** Batch crash-fix, Card 1 (`_run_recompute_baseline` docstring, `millpy-merge-in-subagent.py` lines 211-214)
**Issue:** The function's "Never raises" docstring enumerates failure paths as "no module-wide verify configured, parent branch unresolvable, or the computation itself raising" — the Requirements don't ask to add the newly-handled "status.md absent" case to this list, leaving the docstring incomplete relative to actual behavior post-fix.
**Fix:** Add a docstring update instruction naming the new failure path alongside the existing three, or note explicitly that this is intentionally deferred.

## Verdict

REQUEST_CHANGES
Fix the contradictory test-insertion location in Card 1 before this plan is safe to implement literally.
MILL_REVIEW_END
