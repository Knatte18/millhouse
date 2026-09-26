MILL_REVIEW_BEGIN
# Review: millpy-implement finalize/resume fixes and the red integration suites

```yaml
duration_s: 37.1
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: /home/knatte/Code/millhouse/wts/implement-recovery-and-integration-tests/_mill/discussion.md
date: 2026-09-26
```

## Findings

### [NIT:design] Briefs-dir source left open
**Section:** Decisions / resume-brief-dirty **Issue:** `_in_scope_dirty_stuck` already receives `task_dir` (worktree-relative task directory), yet the fix computes the briefs directory via `_paths.resolve_task_path` with a fallback, without saying which input is authoritative. **Fix:** State that the plan writer picks the source from what `task_dir` actually holds in the nested layout, verified by the reproduction test.

### [NIT:scope] Verified reproduction of #1162 still pending
**Section:** Decisions / resume-brief-dirty **Issue:** The nested-layout mechanism is consistent with the source (prefix test at `startswith("_mill/briefs/")`, repo-root-relative `git diff --name-only`), but the discussion has not reproduced it. The reproduce-first step and finalize-side fallback cover this. **Fix:** None required; the plan must schedule the reproduction before the fix.

## Verdict

APPROVE
Source claims for #1163 and #1162 check out; only two non-blocking NITs remain.
MILL_REVIEW_END
