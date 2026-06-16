MILL_REVIEW_BEGIN
# Review: Fix nested mill layout paths, whole-repo formatter drift, and stacked-branch PR cleanup — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-16
```

## Findings

### [NIT] ROOD-3 test mocks an impossible input for the function under test
**Location:** `plugins/mill/unit_tests/test-cleanliness.py:449-465`
**Issue:** `revert_out_of_scope_drift` calls `_pygit2_util.status_porcelain(worktree, include_untracked=False)`, which can never return `??` entries. ROOD-3 patches `status_porcelain` to return `["?? out_of_scope.txt"]` — the test passes for the right reason (no ` M`/`M `/`MM` match), but it exercises a path that cannot occur in production.
**Fix:** Assert in the test comment that this mocks an unreachable scenario, or replace the mock return with ` D out_of_scope.txt` (a deleted-in-index entry, also not in the revert set) to test a genuinely reachable non-modified status code.

### [NIT] `revert_out_of_scope_drift` silently drops failed reverts from both output lists
**Location:** `plugins/mill/scripts/_cleanliness.py:222-225`
**Issue:** When `git checkout HEAD -- <path>` exits non-zero, the path is neither added to `reverted_paths` nor to `remaining_in_scope_lines`. The caller in mill-go step 2b uses `remaining_in_scope_lines` as the ground truth for blocking; a failed revert of an out-of-scope file causes it to disappear from both lists, so the gate never sees it. The file stays dirty in the working tree.
**Fix:** On non-zero exit from `git checkout`, append the porcelain line to `remaining_in_scope_lines` (treat a failed revert as still-dirty in-scope from the gate's perspective), or re-read porcelain status after the revert loop.

## Verdict

APPROVE
Implementation is correct and complete; two NITs noted, one with a real-world edge-case consequence.
MILL_REVIEW_END
