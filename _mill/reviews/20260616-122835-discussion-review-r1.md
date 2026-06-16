MILL_REVIEW_BEGIN
# Review: Fix nested mill layout paths, whole-repo formatter drift, and stacked-branch PR cleanup

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-16
```

## Findings

### [GAP] mill-start/mill-plan have no worktree_root assignment
**Section:** Scope → Path resolution (mill-start / mill-plan SKILLs)
**Issue:** The scope says "derive `worktree_root` from the hub root, not `git_root`," but `mill-start/SKILL.md` (Entry steps 1-3, Path Setup line 51) and `mill-plan/SKILL.md` (line 21) never define `worktree_root`, `git_root`, or `hub_root` at all — they reference `worktree_root` as an undefined variable. There is no `worktree_root = git_root` line to change (unlike mill-finalize:17, which is explicit).
**Fix:** State that the plan must *add* an explicit `worktree_root = _paths.resolve_hub_path()` (and `git_root`/`hub_root` as needed) to Entry of both SKILLs, not edit a non-existent assignment.

### [GAP] Discussion CLI's find_active_slug still passes git_root
**Section:** Decisions → review-plan-anchor; Technical context → Review CLIs
**Issue:** The decision is "both review CLIs resolve to the same hub root," and plan's `find_active_slug` arg switches to `resolve_hub_path()`. But `millpy-review-discussion.py:88` still passes `git_root` to `find_active_slug`. That function's glob fallback is `(<arg> / "_mill").glob("*.active")` (`_review_common.py:283`), so under a nested layout the discussion CLI looks in `<git_root>/_mill` (nonexistent) while plan looks in `<hub>/_mill`. Scope lists only discussion line 96 (`briefs_dir`), not line 88.
**Fix:** Decide explicitly whether the discussion CLI's `find_active_slug(git_root, …)` should also move to the hub root for symmetry, or document why the divergence is acceptable.

### [NOTE] python-build has no write-mode formatter to scope
**Section:** Technical context → Formatter scoping (#493-A)
**Issue:** The text says scope `ruff format`/`ruff check --fix` to changed files, but `python-build/SKILL.md:17` ships only `ruff check .` (read-only) and `pytest` — no `ruff format` or `--fix` exists today. The scoping edit therefore touches a command that is currently absent.
**Fix:** Clarify the python-build edit is precautionary (add the convention so a future `--fix`/`format` is scoped), since there is no current writer to narrow.

### [NOTE] "owned_paths" referenced as a primitive but is a parameter
**Section:** Technical context → Cleanliness gate (#493-A)
**Issue:** The text lists `owned_paths` among the existing `_cleanliness.py` scope primitives. There is no `owned_paths` function/value; it is only the parameter name of `_filter_to_task_scope` fed from `_parent_diff_names`. The new `revert_out_of_scope_drift` helper must compute the parent-diff set itself via `_parent_diff_names`.
**Fix:** Reword to reference `_parent_diff_names` (the actual source of the owned set), not a nonexistent `owned_paths` primitive.

## Verdict

GAPS_FOUND
Two unresolved callsite ambiguities (SKILL worktree_root definition; discussion CLI find_active_slug root) must be settled before planning.
MILL_REVIEW_END
