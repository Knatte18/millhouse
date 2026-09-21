MILL_REVIEW_BEGIN
# Review: mill-go/mill-merge-in orchestration robustness gaps, round 2 — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-21
```

## Findings

### [BLOCKING:design] Card 3's full-history-fallback success envelope hardcodes a stale `commit_sha`
**Location:** Batch 1, Card 3 (`_forward_output` full-batch-history fallback). **Issue:** the new guard is inserted ahead of BOTH existing demotions (`HEAD == start_sha` and `_is_only_start_batch_commit`), but its success payload always emits `"commit_sha": start_sha`; `_is_only_start_batch_commit`'s own docstring in `_implementer_common.py` (verified: lines ~19-36) states "HEAD != start_sha even when the implementer wrote zero code commits" (the housekeeping commit case) — so when that second demotion is the one being bypassed, `start_sha` is not the actual current HEAD and the reported `commit_sha` is stale/wrong. **Fix:** resolve the actual current HEAD via `git -C <project_root> rev-parse HEAD` (the pattern every sibling success/stuck path in this same function already uses, e.g. `_attach_commit_sha`, verified at lines 395-414) and use that value instead of the `start_sha` parameter.

## Verdict

REQUEST_CHANGES
Card 3's new success envelope must report actual current HEAD, not the `start_sha` parameter, in the housekeeping-commit-only bypass case.
MILL_REVIEW_END
