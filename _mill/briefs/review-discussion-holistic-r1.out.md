MILL_REVIEW_BEGIN
# Review: _verify_baseline.py transient worktrees can be orphaned when the task worktree is force-removed mid-computation

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-09
```

## Findings

### [GAP] Testing section misstates which existing mocked tests reach the prune path
**Section:** ## Testing **Issue:** Claims "none of them reach the new trailing-prune code path (they all raise before it)" — false: `test-worktree.py:246-263` ("is not a working tree", path exists) and `:286-300` (path absent) already use `side_effect=[mock_result, mock_prune]` and exit *without* raising, so they already hit the current fallback-branch prune call and will hit the restructured trailing prune call. **Fix:** Correct the claim to name these 2 of 7 tests as already-prune-exercising, non-raising cases whose two-call mock ordering must survive the restructure.

### [NOTE] Testing section overstates existing real-git coverage of remove_safe
**Section:** ## Testing **Issue:** States remove_safe coverage "already uses a mix of real-git-repo tests for the happy paths" — but in `test-worktree.py` all current `remove_safe` tests (lines 141-300) are mocked; the real-git happy-path tests in the file (`_git_init` + `create`/`move`/`remove`) cover the separate `remove()` function, not `remove_safe`. **Fix:** Note that the new nested-worktree scenario is `remove_safe`'s first real-git test, not an extension of an existing real-git pattern for this specific function.

### [NOTE] Concurrent prune-vs-prune/add contention not named in concurrency rationale
**Section:** ### Decision: centralize-fix-in-remove-safe **Issue:** Rationale covers a sibling's still-live nested worktree not being touched by prune, but doesn't name simultaneous `git worktree prune` calls (or prune racing a concurrent `worktree add`) from parallel `remove_safe` invocations across sibling task-worktree teardowns — a routine scenario for this orchestrator. **Fix:** State explicitly that any such lock contention degrades gracefully via the already-decided prune-failure-is-non-fatal behavior, closing the loop.

## Verdict

GAPS_FOUND
Testing section contains a source-contradicted claim about which existing mocked tests already exercise the prune path.
MILL_REVIEW_END
