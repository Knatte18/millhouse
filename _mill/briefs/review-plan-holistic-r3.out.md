MILL_REVIEW_BEGIN
# Review: Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version unknown)
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [BLOCKING] relocate_and_scaffold's hub_root is not hub_relative_path-aware
**Location:** Batch 2, Card 8 (`_resume_repair.relocate_and_scaffold`) + Card 10 (Phase 1b Step 4)
**Issue:** Step 4 computes `hub_root = _paths.resolve_main_worktree_root(git_root)` and Card 8 copies `.millhouse` from `hub_root / ".millhouse"`. `resolve_main_worktree_root` never consults `hub_relative_path` (unlike `resolve_hub_path`/`resolve_wiki_path`, both of which are stub/config-aware — see `_paths.py:159-226` and `508-560`). For an M2+sub repo where the *main worktree's own* hub `.millhouse` lives in a subdirectory (`_paths.py`'s own documented case, e.g. `src/csharp/NORCE.Models/.millhouse` — exactly the class of repo this task's #728 batches (3/4) already fix elsewhere), `hub_root / ".millhouse"` does not exist. `_worktree.copy_millhouse` silently no-ops when `src` is missing (`if not src.exists(): return` — `_worktree.py:104-105`), so the repaired worktree ends up with an empty `.millhouse/` and no exception is raised — a silent partial failure, exactly the failure class this task exists to eliminate. Compare `millpy-spawn.py:100/149/231-235`, which sources `.millhouse` from `hub = resolve_hub_path()` (hub_relative_path-aware), not from the main worktree root.
**Fix:** Have Phase 1b resolve the true hub `.millhouse` source the same hub_relative_path-aware way `mill-spawn`/`resolve_wiki_path` do (e.g. thread `cfg`/`hub_relative_path` through, or add a stub/config-aware hub resolver callable safely from `main_root`), rather than assuming `hub_root == main_root`; extend Card 9/11's fixtures to cover a main-worktree-hub-in-subdirectory case so this is regression-tested.

## Verdict

REQUEST_CHANGES
Phase 1b's `.millhouse` copy source silently breaks for hub-in-subdirectory main worktrees; everything else verified accurate.
MILL_REVIEW_END
