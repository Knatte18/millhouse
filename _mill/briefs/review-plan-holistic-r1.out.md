MILL_REVIEW_BEGIN
# Review: mill-go's one-shot pre-batch-1 baseline can't cover a task's own later per-batch-baseline capability — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-08-05
```

## Findings

### [NIT] Card 3 doesn't spell out the `overview_text` read step
**Location:** Batch 2 / Card 3, trigger-check condition 4
**Issue:** Requirements say "look up this batch's `file` in `_plan_dag.extract_batch_index(overview_text)`" without stating `overview_text = overview_path.read_text(encoding="utf-8")`, though `overview_path` is an established Path Setup variable and `millpy-implement.py` (in Context) shows the exact call shape.
**Fix:** Add one clause naming the read call explicitly, mirroring `overview_path.read_text(encoding="utf-8")` as used at millpy-implement.py:670-671.

## Verdict

APPROVE
Both batches are complete, source-grounded, and consistent with existing SKILL.md/`_paths`/`_status`/`_plan_dag` conventions; only a trivial documentation nit found.
MILL_REVIEW_END
