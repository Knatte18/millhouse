MILL_REVIEW_BEGIN
# Review: mill-go-base/mill-merge: documented step behavior diverges from underlying script capability — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-21
```

## Findings

### [NIT:consistency] Inconsistent exception chaining in the new detached-HEAD fallback
**Location:** `plugins/mill/scripts/_marker.py:78-79`
**Issue:** The new `except _pygit2_util.GitOpsError: raise MarkerError("detached HEAD or non-branch state")` neither binds `as e` nor re-raises `from e`, whereas every other `except _pygit2_util.GitOpsError` clause in this same function (e.g. lines 72-73, 130-131) binds `as e` and re-raises `from e`. Not required by the batch's own decision text (which only pins the message string), but it is a local style deviation from the file's established convention within the very function being edited.
**Fix:** Bind `as e` and add `from e` to the fallback raise for consistency with the rest of `_marker.py`.

## Verdict

APPROVE
All three batches' cards are fully and correctly realised; cross-batch contracts, shared decisions, and test coverage check out.
MILL_REVIEW_END
