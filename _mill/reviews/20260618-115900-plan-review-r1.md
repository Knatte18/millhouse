MILL_REVIEW_BEGIN
# Review: Fix nested-junction teardown, Windows verify gate in merge-in, and review-plan --round threading — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-18
```

## Findings

### [NIT] Discussion with-existing fixture filename not explicitly specified
**Location:** Batch 3 / Card 7 (`review-discussion-finalize-round-with-existing`)
**Issue:** The card specifies the seed file `20260618-120000-plan-review-r1.md` for the plan with-existing case and says to "use `"discussion"` wherever `"plan"` appears in mock targets," but the fixture filename is not a mock target, so an implementer could add a `plan-review` file in the discussion case — `discover_round(..., "discussion", "holistic")` would then ignore it (RE_SIMPLE type mismatch) and return 1, failing the `round_n == 2` assertion.
**Fix:** State explicitly that the discussion with-existing case seeds a `...-discussion-review-r1.md` file (not `plan-review`) so RE_SIMPLE counts it for `review_type="discussion"`.

### [NIT] review-plan finalize line reference off by one
**Location:** Batch 3 / Card 5
**Issue:** The card says `"round": args.round` is at "Line 190" but it is actually line 191 in the current source (line 183 `round_n=args.round` is correct).
**Fix:** Update to "Line 191" or drop the absolute number; the textual `"round": args.round` description is already unambiguous.

## Verdict

APPROVE
The plan is accurate against source -- function signatures (`strip_all_in_worktree`, `_posix_shell_run_args`, `discover_round`), the three merge-in call sites (lines 175/274/341), import lists, the `args.round` occurrences, and the round-equivalence invariant all verify correctly; the two NITs are non-blocking refinements.
MILL_REVIEW_END
