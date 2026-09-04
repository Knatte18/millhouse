MILL_REVIEW_BEGIN
# Review: millpy-implement/bg: Windows baseline-worktree teardown (WinError 145) and stale liveness reporting — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-04
```

## Findings

### [NIT:scope] apply_plan's `.parent.parent` wt_path recovery not exercised end-to-end
**Location:** `plugins/mill/scripts/millpy-cleanup.py:798`, tested at `plugins/mill/unit_tests/test-cleanup.py:216-288`
**Issue:** `apply_plan`'s orphan-baseline-dir loop derives `wt_path` from `dir_path.parent.parent` and passes it as `cwd` to `_apply_orphan_baseline_dir`. `test_apply_orphan_baseline_dir`'s WorktreeLockedError/WorktreeError sub-cases invoke this through `apply_plan` but never assert the `cwd` kwarg `remove_safe` actually received, so the path-arithmetic assumption is only exercised via the earlier direct-call sub-case (which passes `wt_path` explicitly), not through `apply_plan`'s own derivation.
**Fix:** Capture the mocked `remove_safe` call's `cwd` kwarg in those two sub-cases and assert it equals `wt_path`.

## Verdict

APPROVE
All 5 batches match their plan cards precisely; cross-batch contracts (start_sha/status_path/batch_name threading, junctions_cfg={}, circular-import avoidance) verified correct.
MILL_REVIEW_END
