I have verified all major source claims in the discussion. Every cited line reference, function signature, docstring, and template location checks out accurately. Below is my review.

MILL_REVIEW_BEGIN
# Review: Fix agent-mode dispatch races and pipeline gaps

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-02
```

## Findings

### [NOTE] Baseline stage must bypass batch-index resolution
**Section:** Decisions › baseline-aware module-wide verify gate
**Issue:** `millpy-implement.py:239-242` hard-fails (`return 1`, "batch not found") on a missing `batch_name` *before* `module_wide_verify_cmd` is read at :266, so a `--stage baseline` branch merely added after :266 would never be reached with `batch_name=None`.
**Fix:** State that the new baseline stage must be dispatched ahead of the existing batch-entry/card-count resolution block (:239-253), not appended after it, so the task-scoped stage never triggers batch resolution.

## Verdict

APPROVE
Scope, decisions, failure modes, and testing are fully specified; all source claims verified accurate.
MILL_REVIEW_END