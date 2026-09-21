MILL_REVIEW_BEGIN
# Review: mill-go/mill-merge-in orchestration robustness gaps, round 2 — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-21
```

## Findings

### [BLOCKING:scope] Card 2 Requirements cites two files absent from Context/Edits
**Location:** Batch 1, Card 2 (`_fixer_logic_ancestor_override`). **Issue:** Requirements asserts a mechanism claim ("confirmed by reading both callers") about `` `millpy-fix.py` ``'s `finalize_from_output` call (`start_sha=args.start_sha`, no `card_ids`) and about `` `millpy-merge-in-subagent.py` ``'s two `finalize_from_output` call sites (verified against source: `millpy-fix.py:478-481` and `millpy-merge-in-subagent.py:383-432` — the claims are accurate, but neither file is listed in Card 2's `Context:` (currently only `_status.py`, `_subprocess_util.py`) or `Edits:`). **Fix:** Add `millpy-fix.py` and `millpy-merge-in-subagent.py` to Card 2's `Context:` list so the implementer can independently verify the fixer-only scoping claim the new guard's safety depends on.

### [NIT:consistency] Card 7 names the wrong aggregator function
**Location:** Batch 3, Card 7. **Issue:** Requirements says "Register the new check in the `validate()` aggregator's Go-specific check block" but `_plan_validate.py` has no function named `validate()` — the aggregator is `run()` (verified: `_plan_validate.py` line 4430, `def run(...)`; `validate()` is a distinct function in `_plan_dag.py`). **Fix:** Say "the `run()` aggregator" instead of "the `validate()` aggregator".

## Verdict

REQUEST_CHANGES
Card 2's Context omits two files its own Requirements cites as load-bearing evidence for the guard's safety.
MILL_REVIEW_END
