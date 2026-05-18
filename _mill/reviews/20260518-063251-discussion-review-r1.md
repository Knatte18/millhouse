# Review: 64 (A) — Small infra fixes batch 9

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-18
```

## Findings

### [GAP] _review_plan.py rounds:0 fix missing from scope
**Section:** `## Scope` / `### rounds:0 skip semantics (#327)`
**Issue:** The Decision for rounds:0 explicitly names `_review_plan.py` as one of three files to fix, but the scope entry for `_review_plan.py` lists only "add repeated-finding detection (#323)". Verified: `_review_plan.py` lines 127 and 440 have the same `round_n > max_rounds` guard with no rounds==0 early-out — the bug exists there too.
**Fix:** Add `fix rounds:0 error (#327)` to the `_review_plan.py` scope bullet so the plan writer includes it alongside the repeated-finding work.

### [NOTE] Third `_deep_merge` copy in _test_registry.py unaddressed
**Section:** `### _deep_merge None-clobber (#342)`
**Issue:** `grep` finds a third `_deep_merge` at `_test_registry.py:20` with the same None-clobber pattern. The decision scopes "both `_review_common._deep_merge` and `_config.deep_merge`" only.
**Fix:** Add a line confirming whether `_test_registry._deep_merge` is intentionally excluded (test-only code unlikely to encounter None overlays) so the plan writer doesn't have to guess.

## Verdict

GAPS_FOUND
Scope entry for `_review_plan.py` is missing the rounds:0 fix that the Decision section requires.