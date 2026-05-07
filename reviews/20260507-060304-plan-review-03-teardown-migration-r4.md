# Review: 12 (C) — Restructure hub junction layout — 03-teardown-migration

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 03-teardown-migration
date: 2026-05-07
```

## Findings

### [NIT] HUB_PATH diverges from _build_tokens for task worktrees
**Step:** Card 11, Req 4e — task worktree token dict
**Issue:** Plan sets `HUB_PATH: str(hub_root)` (main worktree) but `_build_tokens` in `millpy-spawn.py` sets `HUB_PATH = str(dest_hub) = str(wt_path)` for each task worktree. New junction templates (`.wiki: <WIKI_PATH>`, `.portals: <WIKI_PATH>/active/<SLUG>/`) don't reference `<HUB_PATH>`, so there is no runtime impact today, but the comment "matches the full `_build_tokens` pattern" is misleading.
**Fix:** Either change `HUB_PATH: str(hub_root)` to `HUB_PATH: str(wt_path)` for task worktrees, or drop the claim that it replicates `_build_tokens` exactly.

### [NIT] Dry-run guard unspecified for wiki push in _step_rename_junctions
**Step:** Card 11, Req 4e and 4g
**Issue:** Req 4g says "perform no writes. Return." but doesn't specify where in the function the dry-run check fires. `write_wiki_active_task_md` commits and pushes to the wiki (not a `_run`-wrapped subprocess); if the dry-run guard is placed after this call, `--dry-run` would still push.
**Fix:** Req 4g should clarify that the guard fires before the per-worktree loop (early-exit after summary logging), not after individual ops.

### [NIT] Empty-commit risk when no root working-state files exist
**Step:** Card 11, Req 4e — move working state to task/
**Issue:** After the `git mv` loop, a single `git commit` is issued unconditionally. If all four paths (`status.md`, `discussion.md`, `plan/`, `reviews/`) are absent at the root, no `git mv` is staged and the commit fails with exit 1, aborting the entire migration via `_run`'s `sys.exit(1)`. Pathological in practice (all active old-layout worktrees have at least `status.md`) but real for edge cases.
**Fix:** Guard the commit with a check (e.g., `any_moved` flag) and skip the commit if nothing was staged.

## Verdict

APPROVE
No blocking issues; three low-risk NITs, none affecting correctness for normal operating conditions.