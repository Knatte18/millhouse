MILL_REVIEW_BEGIN
# Review: Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-07-28
```

## Findings

### [GAP] Testing section never tests the 6th site's blocking_count fix
**Section:** Testing (`_review_plan.py::run()` TDD paragraph) vs. Decision `nit-count-fix-mechanism` / round-3 Q&A
**Issue:** Round-3's Q&A expanded `_scan_approved_batches()`'s 6th-site fix to compute `blocking_count` (not just `nit_count`), reasoning a carried-forward APPROVE'd batch could carry an unrecognized-severity finding — but the Testing section's Test 8 extension asks only for a `[NIT]`-carrying fixture + `nit_count` assertion, leaving that newly-required `blocking_count` computation completely untested — the exact vacuous-test trap round-4 already caught for `nit_count` on Test 14/29, recurring here for the sibling counter.
**Fix:** Add a carried-forward APPROVE'd fixture in Test 8 with a real `[BLOCKING]`/off-vocabulary finding and assert the aggregate `blocking_count` reflects it, not silently 0.

### [GAP] Technical context's 5-site map contradicts, and omits, the Decision
**Section:** Technical context (the 5 inline `blocking_count` computations list) vs. Decision `nit-count-fix-mechanism`
**Issue:** The list still directs the resume-disk-scan block (~738-749) to receive "narrow patch, add `nit_count` line only," directly contradicting the Decision's explicit "left untouched" / "Rejected: patching the resume-disk-scan site's `nit_count`" (verified: `_disk_reviews` is built and read but never merged into `reviews` anywhere in `run()` — no `reviews.append`/`extend(_disk_reviews)` exists); the list also has no 6th bullet for `_scan_approved_batches()` (`_review_plan.py:70-119`), which the Decision (as corrected in rounds 2-3) requires touching for both `blocking_count` and `nit_count`.
**Fix:** Change the resume-disk-scan bullet's action to "no code change — output discarded, out of scope" and add a 6th bullet for `_scan_approved_batches()` lines 70-119 matching the Decision's fix.

## Notes

### [NOTE] #720's "genuinely new" finalize_scope() test overlaps existing coverage
**Section:** Testing (#720 coverage, item 2)
**Issue:** `test-review-common.py` (~lines 2324-2345) already has a `finalize_scope()`-direct test asserting `blocking_count == 2, nit_count == 1` via the same unconditional `blocking_count += count_unrecognized_severity_findings(...)` path (mixed with a real `[BLOCKING]`/`[NIT]` rather than isolated), so the proposed isolated zero-BLOCKING/NIT case is a narrower variant, not wholly new ground.
**Fix:** Reframe as "extend/complement the existing finalize_scope() fold-in test" rather than "genuinely new" coverage.

### [NOTE] New plugin.json validator check has no Deletes: trigger
**Section:** Decision `platform-claim-verification`
**Issue:** The check fires only when a batch's `Creates:`/`Edits:` touches `plugins/mill/agents/`; a batch that only `Deletes:` an agent-definition file (and should remove its `plugin.json` array entry) is never required to show `plugin.json` in Context/Edits, leaving the symmetric array/directory-mismatch failure mode uncovered.
**Fix:** Either extend the trigger to include `Deletes:` touching `plugins/mill/agents/`, or record the narrower scope as a deliberate limitation alongside the other deferred platform-claim categories.

## Verdict

GAPS_FOUND
Two GAPs: Testing undertests the 6th-site blocking_count fix; Technical context's site map contradicts and omits Decision content.
MILL_REVIEW_END
