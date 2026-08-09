MILL_REVIEW_BEGIN
# Review: _verify_baseline.py transient worktrees can be orphaned when the task worktree is force-removed mid-computation — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (per harness metadata; independent self-assessment would have guessed "Claude Sonnet 4.5")
reviewed_file: plan/
date: 2026-08-09
```

## Findings

### [NIT] Nested worktree parent dir not explicitly created in Card 2's test
**Location:** Batch 1 / Card 2, step 3 **Issue:** `nested_path = task_wt / ".scratch" / "nested"` is passed straight to `git worktree add --detach`, without first `mkdir`-ing `.scratch/`, unlike the real `_checkout_parent_branch` which explicitly does `scratch_dir.mkdir(parents=True, exist_ok=True)`. **Fix:** Add an explicit `(task_wt / ".scratch").mkdir()` before the `git worktree add` call for determinism across git versions, mirroring the production code path it's meant to emulate.

### [NIT] Regression test doesn't pin down which removal branch executed
**Location:** Batch 1 / Card 2, steps 4–6 **Issue:** The test only asserts `task_wt` is gone and `nested_path` is absent from `list_worktrees(hub)`; it doesn't confirm the outer removal went through the direct-success branch (`returncode == 0`) rather than the fallback branch, which already called `prune` under the pre-fix code — so if `git worktree remove --force` unexpectedly hit a fallback-eligible stderr pattern on some git version, the test could pass even without Card 1's fix. **Fix:** Capture/assert on the `[worktree] remove_safe: removed via git (...)` stderr message (or similar) to confirm the success path was exercised.

## Verdict

APPROVE
Restructure and test plan are internally consistent, accurately grounded in source, and faithfully implement all three Shared Decisions.
MILL_REVIEW_END
