MILL_REVIEW_BEGIN
# Review: mill-plan autonomy guidance and validation gaps: fork scope violations, missing anti-pause guidance, no mechanical Context/Edits completeness check

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed)
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] context-completeness has no escape valve for heuristic false positives
**Section:** Decisions > `context-completeness` validator check design (#742)
**Issue:** A backtick token ending in a listed extension or containing `/` (e.g. `` `response.json` `` as a JSON-body attribute access, or a Go slash-qualified identifier) is not necessarily a file path, but the check has no way to distinguish this from a real omitted reference; the fix-table only handles the Deletes:/Moves:-legitimate-omission case, not "this token isn't a file at all."
**Fix:** The naive mechanical remedy ("add to Context:") is actively harmful here — adding a non-existent path to Context: will then trip the existing `non-existent-path` check (`_plan_validate.py:706-714`) on the next pass, hitting the two-pass non-progress cap with no documented resolution. Add an explicit fix-table branch (or a "halt, not mechanically fixable" row) for this case.

### [GAP] Batching decision's "no shared Context:" premise is false for #741/#743
**Section:** Decisions > Batching left to mill-plan (housekeeping)
**Issue:** The rationale claims the three gaps' code is disjoint ("SKILL.md prose for #741 and #743 ... with no shared Context:"), but #741 and #743 both edit `mill-plan/SKILL.md` (different sections: Phase: Plan vs. Phase: Plan Review). If mill-plan's batch-sizing splits them into two independent (non-`depends-on`) batches, `_check_parallel_modifies_overlap` (`_plan_validate.py:998-1060`) compares batches' `Edits:` sets pairwise and will flag the shared `mill-plan/SKILL.md` path as a parallel-modifies conflict, since it does not distinguish which section of a file is touched.
**Fix:** Either mandate that #741 and #743 land in the same batch (two cards, one file, no cross-batch overlap) or explicitly require a `depends-on` edge between whichever batches carry them, so the plan-writer isn't left to discover this via a validator failure mid-plan-writing.

## Verdict

GAPS_FOUND
Two mechanically-groundable gaps: an unhandled validator false-positive path and a batching premise contradicted by an existing check.
MILL_REVIEW_END
