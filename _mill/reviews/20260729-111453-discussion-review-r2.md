MILL_REVIEW_BEGIN
# Review: Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] merge-in-subagent.py fix diagnosis misreads the actual `load_config` call site
**Section:** Decisions -> load-config-fix-mechanics
**Issue:** The decision claims that fixing `project_root = Path.cwd()` (line ~338) to `_paths.resolve_hub_path()` means "the load_config call itself needs no further change once project_root is correct." Verified against source: the actual call at line 345 is `_review_common.load_config(git_root, mill_dir)` — arg1 is `git_root` (`_paths.resolve_git_root()`, defined line 341), not `project_root`. `project_root` only feeds `mill_dir` (arg2, line 338). Fixing `project_root`'s definition alone leaves arg1 as the outer git-repo root — the exact bug pattern from the Problem statement (#728) — unfixed.
**Fix:** Update the decision to also require changing the call itself, e.g. `load_config(project_root, mill_dir)` (swapping `git_root` for `project_root`, in addition to fixing `project_root`'s own definition) — otherwise a plan writer following this decision literally produces an incomplete fix for the file that is arguably the primary #728 repro target.

### [NOTE] `_plan_validate.py:1455` citation points to a different function than `run()`
**Section:** Decisions -> load-config-validate-plan-included; Technical context (load_config call sites bullet)
**Issue:** The "also doubles as the hub_root" docstring quote at line 1455 belongs to `_check_verify_not_isolated`'s `project_root` parameter, not `_plan_validate.run`'s own docstring (`run` is defined at line 2001; its docstring at line ~2027 says only "Root of the project (typically the worktree root)"). The underlying conclusion still holds (run threads its `project_root` param down to that helper), but the citation attributes the quote to the wrong function.
**Fix:** Correct the citation to reference `_check_verify_not_isolated`'s docstring, or cite `run`'s own docstring text instead.

## Verdict

GAPS_FOUND
One GAP: merge-in-subagent.py's load_config fix instructions omit the actual arg1 swap needed.
MILL_REVIEW_END
