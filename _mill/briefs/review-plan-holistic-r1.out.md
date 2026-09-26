MILL_REVIEW_BEGIN
# Review: Post-merge teardown: keep PR notes, remove checkpoint branches — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-26
```

## Findings

### [BLOCKING:scope] Card 3 omits existing tests that Card 2 breaks
**Location:** Batch 1 / Card 2 + Card 3 **Issue:** `test-cleanup.py` has existing cases that filter recorded git argv for `"branch" in c and ("-d" in c or "-D" in c)` and assert `len(...) == 1` (around lines 616-620, 785-791, 927); the new `branch -D mill-checkpoint-...` call from `delete_checkpoint_branch` (via the shared `_subprocess_util.run` patch) makes the count 2, so batch 1's own `verify:` fails. **Fix:** Card 3 Requirements must name those existing assertions and say to update them (exclude `mill-checkpoint-` argv, or expect two calls).

### [NIT:design] Card 3 tests rely on a call-specific mock the plan does not state
**Location:** Batch 1 / Card 3 **Issue:** `delete_checkpoint_branch` first runs `rev-parse --verify --quiet`, and returns True without running `branch -D` when that exits non-zero, so a blanket non-zero mock never reaches the `branch -D` call the "non-zero does not raise" case targets. **Fix:** State that the fake `run` returns 0 for `rev-parse` and non-zero only for `branch -D`.

### [NIT:scope] pr-reap path not covered by a test
**Location:** Batch 1 / Card 3 **Issue:** The discussion's Testing section lists a pr-reap record case; the card covers only the worktree and in-place records. **Fix:** Add a pr-reap case or state the delegation makes it redundant.

### [NIT:consistency] Step label "5.5" collides with historical naming
**Location:** Batch 2 / Card 4 **Issue:** `mill-merge-in/SKILL.md` step 5 prose cites a past "Step 5.5 git add" fix commit (7a972fbf), so a new "### 5.5. Delete checkpoint" heading is ambiguous with that reference. **Fix:** Note the ambiguity or label the step differently (e.g. 5b).

### [NIT:consistency] Card 4 Context lists an unused file
**Location:** Batch 2 / Cards 4 and 6 **Issue:** `_finalize_cleanup.py` is in Context for Card 4, which edits only prose and uses inlined shell. **Fix:** Drop it from Card 4 Context.

## Verdict

REQUEST_CHANGES
Card 2's checkpoint call breaks existing exact-count branch-delete assertions in test-cleanup.py that Card 3 does not address.
MILL_REVIEW_END
