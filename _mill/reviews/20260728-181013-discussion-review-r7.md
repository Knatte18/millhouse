MILL_REVIEW_BEGIN
# Review: Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-07-28
```

## Findings

### [GAP] Holistic-normal refactor site lacks non-vacuous nit_count test
**Section:** Testing (opening bullet) / Technical context ("Holistic normal... extend with nit_count")
**Issue:** Testing's opening sentence promises real-`[NIT]`-backed coverage for "each of the 4 `finalize_scope()`-refactored sites," but the concrete plan only augments Test 14/29's per-batch texts and adds cases for the two NEED_CONTEXT holistic branches (Test 7, no-resolve) — the "holistic normal" block (`_review_plan.py:995-1013`, the only one of the 4 sites reached by Test 14's holistic leg, which stays `APPROVE_TEXT`) never gets a fixture with a real `[NIT]`/`[BLOCKING]` heading; grep across the whole file confirms zero such headings exist outside Test 14/29's per-batch texts.
**Fix:** Add a `[NIT]` (or `[BLOCKING]`) heading to a holistic-scope mock (e.g. Test 14's holistic leg, or a new test) and assert that review entry's own `blocking_count`/`nit_count`, not only the per-batch-driven aggregate.

### [NOTE] "Every check has a fix-table row" claim is inaccurate
**Section:** Technical context, final bullet
**Issue:** The bullet states the Step 1.5 fix table (`mill-plan/SKILL.md:126-147`, verified 20 rows) already has a row for every `_plan_validate.py` check ("confirmed by reading the full table"), but `_plan_validate.py::run()` (its Public API) also emits `depends-on-batch-mismatch`, `verify-full-suite`, `verify-malformed-cwd`, and `verify-mixed-cwd` as real `errors[].check` values with no matching table row.
**Fix:** Reword to "every check should have a row" (an intended convention, not an already-verified invariant); the Decision to add one new row for `plugin-manifest-context-missing` is unaffected.

## Verdict

GAPS_FOUND
Holistic-normal refactor site — one of the 4 enumerated sites — lacks genuine (non-zero-fixture) test coverage in the Testing plan.
MILL_REVIEW_END
