MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: entry, phase-gate, finalize, and re-entry path gaps

```yaml
duration_s: 297.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; cannot verify exact point-release from inside the session)
reviewed_file: _mill/discussion.md
date: 2026-08-13
```

## Findings

### [BLOCKING:design] hub_root fix leaves worktree_root's identical forward-reference bug
**Section:** Decision "Entry: bind `hub_root` explicitly (#839, #826)" **Issue:** `_config.load_config(hub_root, worktree_root)` needs both args at step 2, but `worktree_root` is bound only in `**Path Setup.**` (SKILL.md:47), which is positioned after step 3 — after step 2 already needs it. Verified against `_config.py:221` (`load_config(hub_root: Path, worktree_root: Path)`). This is the exact same "referenced before bound, unsatisfiable as written" defect class #839 reports for `hub_root`, on the sibling argument, left untouched by the decision. **Fix:** Either bind `worktree_root = _paths.resolve_hub_path()` in step 1 alongside `hub_root`/`git_root`/`wiki_path` (mirroring the `hub_root` fix), or move `**Path Setup.**`'s binding ahead of step 2.

### [BLOCKING:design] `blocked` row's `discover_round` call needs `reviews_dir`, which isn't bound at Entry time
**Section:** Decision "Max-rounds block: add a `blocked` re-entry row (#832)" **Issue:** The row computes `N = _review_common.discover_round(reviews_dir, "plan", "holistic")` at Entry step 4, but `reviews_dir` is explicitly punted to Phase: Plan Review's own `**Path Setup (Plan Review).**` (SKILL.md:263: `reviews_dir = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])`); SKILL.md:51 states plainly "`reviews_dir` will be derived during ... Phase: Plan Review (reads)," not Entry. The decision never says how the `blocked` row obtains `reviews_dir` before that point. **Fix:** State explicitly that the `blocked` row inlines the same `_paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])` expression before calling `discover_round` — `worktree_root`/`cfg` are already bound by Entry step 4, so this is a one-line addition, not a restructure.

## Verdict

REQUEST_CHANGES
Two unaddressed forward-reference ordering gaps (worktree_root, reviews_dir) of the exact bug class this task fixes elsewhere.
MILL_REVIEW_END
