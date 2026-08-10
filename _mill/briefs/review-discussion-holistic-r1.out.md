MILL_REVIEW_BEGIN
# Review: mill-merge-in --recompute-baseline crashes uncaught on absent status.md

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; brief specifies "sonnethigh" as authoritative)
reviewed_file: _mill/discussion.md
date: 2026-08-10
```

## Findings

### [NIT:consistency] Technical Context misattributes require_status_path call site
**Section:** Technical context, "Sibling function for context" bullet **Issue:** Claims `_run_baseline_stage` (millpy-implement.py) calls `_paths.require_status_path` at line 561; source shows that call is in `main()` (line 561, inside the 443+ function), and `_run_baseline_stage` (216-442) instead receives an already-resolved `status_path` as a parameter and never calls `require_status_path` itself. **Fix:** Correct the attribution to `main()` before plan writing; the underlying point (this call site correctly treats absence as a hard startup error, opposite of this task's target behavior) still holds regardless.

## Verdict

APPROVE
Decisions, scope, and technical claims verified against source; one minor misattribution noted as non-blocking.
MILL_REVIEW_END
