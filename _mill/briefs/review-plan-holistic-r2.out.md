MILL_REVIEW_BEGIN
# Review: Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-30
```

## Findings

### [BLOCKING] Card 11 leaves stale "Clean mid-work stop" routing
**Location:** Batch 4 / Card 11 (mill-go SKILL.md ~line 129)
**Issue:** Card 11 only edits Agent-mode step 3 and `### Stuck escalation`, but the agent-mode mid-batch handler is the "Clean mid-work stop (implementer only)" block, which still says finalize emits `stuck_type: transient` and routes `commits_made > 0` to the skip-to-cleanliness branch — after Batch 1, finalize emits `incomplete` on that exact path, so the SKILL self-contradicts and the primary #574 agent-mode scenario still accepts partial work as done.
**Fix:** Add the "Clean mid-work stop" block to Card 11's edits and rewrite it to route the new `incomplete` envelope to the warm-SendMessage / `--resume-incomplete` recovery instead of transient skip-to-cleanliness.

### [NIT] Card 7 does not preserve the cleanliness snapshot on resume
**Location:** Batch 2 / Card 7(b) (millpy-implement.py line 293)
**Issue:** Card 7(b) skips the staging+commit block on `--resume-incomplete` but does not skip `_cleanliness.capture_snapshot`, so the original batch-start baseline snapshot is overwritten with post-partial-work state and, with the commit block skipped, may be left uncommitted — corrupting the finalize new-dirt baseline.
**Fix:** On `--resume-incomplete`, also skip `capture_snapshot` and reuse the existing snapshot file written by the original dispatch.

## Verdict

REQUEST_CHANGES
Plan is sound and well-grounded; Card 11 must reconcile the stale agent-mode clean-stop routing.
MILL_REVIEW_END
