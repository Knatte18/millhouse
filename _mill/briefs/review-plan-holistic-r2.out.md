All major claims check out against source. The plan is technically sound.

MILL_REVIEW_BEGIN
# Review: Fix batch-name sanitization (colon/slash on Windows) and implementer skill loading — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-15
```

## Findings

### [NIT] Card 7 mirrors a runner from a file not in Context
**Location:** Batch 2 / Card 7
**Issue:** Requirements say "mirror the runner in `test-agent-dispatch.py`", but that file is in neither Card 7's `Context:` nor `Edits:`, so a strict implementer cannot open it.
**Fix:** Add `plugins/mill/unit_tests/test-agent-dispatch.py` to Card 7's `Context:` (it is already in Cards 1/2/4, so the pattern is otherwise reachable; this card is the only one that references it without listing it).

### [NIT] Batch-2 verify omits the other parse_batch_refs caller
**Location:** Batch 2 / Card 4 verify
**Issue:** Card 4 changes `parse_batch_refs`'s signature; `_plan_validate.py` also calls it (single-arg), but only `test-review-common.py` guards the refactor. The default tuple preserves behavior, so this is not a defect — just an untested second caller.
**Fix:** Optional — the default-tuple guarantee makes `_plan_validate.py` safe; no action strictly required.

## Verdict

APPROVE
Plan is accurate, complete, and source-grounded; only two minor context/test nits.
MILL_REVIEW_END
