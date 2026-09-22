MILL_REVIEW_BEGIN
# Review: compute_baseline: use the task worktree's own pre-edit state, not a parent-branch checkout

```yaml
duration_s: 200.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md (round 4)
date: 2026-09-22
```

## Findings

### [BLOCKING:design] Guard path prefixes have no stated coordinate space
**Section:** Decisions -> `preflight-precondition-guard`, `preflight-dirt-warning`
**Issue:** Both decisions test paths against bare `_mill/` / `.millhouse/` prefixes, but `git status --porcelain` and `git diff --name-only` emit repo-root-relative paths while those prefixes are hub-relative; in a nested-hub layout (`project_root` below `git_root` — the case `millpy-implement.py:76-91`'s `_relative_cwd_fragment` and the discussion's own `git_root` vs `project_root` gotcha exist for) every mill-plan write lands as `<hub-frag>/_mill/...`, so the exclusion never matches, the guard reports `"worktree is not pre-edit"`, and the whole capture is silently skipped for the entire task (and the dirt warning fires on every `_mill/` write).
**Fix:** State which root the two git commands run against and that the exclusion prefixes are re-anchored to the hub fragment (`project_root.relative_to(git_root)` / `_paths`) before comparison, with flat layouts as the degenerate case.

### [NIT:decision] Clearing helper left as an either/or
**Section:** Scope -> In -> `_status.py`
**Issue:** The bullet defers between `set_batch_field(..., None)` and a new `clear_batch_verify_baselines`, conditional on whether the existing writer expresses removal — `_status.py:1086-1087` shows it does (a `None` value pops the key, and `_serialise_batches` omits only `None`).
**Fix:** Name `set_batch_field(..., None)` as the mechanism and drop the alternative helper.

### [NIT:design] Partial-failure policy for the eager per-batch capture unstated
**Section:** Decisions -> `eager-not-lazy`; Gotchas
**Issue:** `compute_batch_baselines` evaluates its whole `commands` list in one loop and propagates `subprocess.TimeoutExpired`, and its docstring assumes a caller that drives one batch per call with its own try/except; the discussion never says whether one pair's timeout/exception aborts the remaining batches' captures or only that pair's.
**Fix:** State the driver shape — per-batch call with a shared `pair_cache` and per-batch exception isolation — so one hung suite leaves only its own batch unset.

### [NIT:consistency] Rejected alternative mischaracterises `status_path`
**Section:** Decisions -> `capture-set-equals-gate-set` (Rejected)
**Issue:** "Passing `status_path` ... narrows the filter to nothing useful" understates it: `_plan_dag.py:663` skips every batch whose state is not `approved`, so at pre-flight the enumeration returns `[]`, not a narrowed list.
**Fix:** Restate the rejection as "would return an empty capture set at pre-flight".

## Verdict

REQUEST_CHANGES
Guard's path-prefix coordinate space is unspecified and silently disables capture in nested-hub layouts.
MILL_REVIEW_END
