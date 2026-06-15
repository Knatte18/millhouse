MILL_REVIEW_BEGIN
# Review: Fix mill-ghissues-to-tasks to refuse fold-ins into done and deferred tasks — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-15
```

## Findings

### [NIT] Stale "phase-guard" wording survives in exit-codes docstring
**Location:** Batch 1, Card 2
**Issue:** Card 2 scopes the docstring rewrite to lines 10-17 + the operation-order line ~11, but `millpy-fold.py` line 30 (`1 — validation, environment, phase-guard, or GH-state error`) also carries "phase-guard" wording the card does not call out.
**Fix:** Extend Card 2's docstring sweep to the exit-codes block (line ~30) so no "phase-guard" prose remains module-wide.

### [NIT] Card 3 item (6) references a nonexistent "execution/call list"
**Location:** Batch 1, Card 3
**Issue:** `test-fold.py`'s `main()` is a linear sequence of inline `try/except` blocks, not separate functions in a call/execution list; item (6) instructs registering "every new test function in the `main()` runner's execution/call list," a structure that does not exist.
**Fix:** Reword item (6) to "add each new case as an inline `try/except` block inside `main()` before the final `return 0`," matching the existing pattern item (5) already cites.

## Verdict

APPROVE
Decisions faithfully implemented; DAG, numbering, and context-completeness pass; only two minor wording NITs.
MILL_REVIEW_END
