Now I have everything I need for a thorough review. Let me compile the findings.

MILL_REVIEW_BEGIN
# Review: Fix implement finalize correctness: mid-batch stop recovery, commit-count guard, and empty-commit detection — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-28
```

## Findings

### [NIT] Card 4 line number off by one
**Location:** Batch 2 / Card 4
**Issue:** The plan says the "One commit per card." bullet is at line 54; in the actual `implementer-brief.md` it is line 55 (the `git-commit` skill bullet occupies line 54).
**Fix:** Correct to "line 55", or rely solely on the text anchor which is already provided and is unambiguous.

### [NIT] Case 39 test assertions too weak to confirm guard fires
**Location:** Batch 1 / Card 3 (Case 39)
**Issue:** The plan asserts only `status: stuck` and `stuck_type: logic` for the inference-path guard test. If the snapshot file is malformed (e.g. wrong format from the "e.g. write git status output" approach) and `compute_new_dirt` raises or returns non-empty, the entire inference branch is skipped and the fallback emits `stuck/logic` with reason "no structured report" — causing the weak assertions to pass without the new guard ever firing.
**Fix:** Add a `reason` assertion that matches the guard's specific message (e.g. `"start-batch commit"` or `"only batch-start commit since start_sha"`), and use `_cleanliness.capture_snapshot()` to create the snapshot file (matching every other test that exercises the snapshot-present path) rather than the ambiguous "e.g. write git status output" approach.

## Verdict

APPROVE
Plan is structurally sound; all four call sites correctly identified, Shared Decisions faithfully mapped, DAG is valid, and no BLOCKING issues found.
MILL_REVIEW_END
