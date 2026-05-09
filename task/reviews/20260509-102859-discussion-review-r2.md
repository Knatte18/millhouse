Now I have all the information needed. Writing the review.

---

# Review: 35 (A) — Centralize path resolution across all three modes

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-09
```

## Findings

### [NOTE] ActiveError during in-place check — fallthrough vs. crash
**Section:** § Decisions / helper-bodies
**Issue:** The proposed `resolve_active_worktree` body calls `_active.read_all(hub_dir / ".millhouse")` (cwd's marker) without catching `ActiveError`. If the cwd has no active marker — a valid state for any cross-worktree caller not currently inside an active task — the function crashes instead of falling through to the `container / "wts" / slug` branch.
**Fix:** State explicitly whether `ActiveError` from the in-place check should be caught and treated as "not in-place" (fall through), or whether callers are contractually required to run from within an active task. The decision's gotcha note about propagating `ActiveError` refers to the marker check on the *found* worktree; the in-place detection's read is a different call site.

### [NOTE] `resolve_worktrees_dir` / `container/"wts"` inconsistency
**Section:** § Decisions / helper-bodies
**Issue:** `_inplace.is_inplace` checks worktree-dir presence via `resolve_worktrees_dir(cfg, git_root)`, which supports a configurable `cfg["spawn"]["worktrees_dir"]` override (confirmed: `_paths.py:155`). The proposed fallthrough branch hardcodes `container / "wts" / slug`. If `spawn.worktrees_dir` is ever set to a non-default path, `is_inplace` and `resolve_active_worktree` would disagree on where to look, causing spurious `ActiveWorktreeNotFound`.
**Fix:** One sentence is enough: note that the fallthrough branch assumes the standard container-form layout and that any future `spawn.worktrees_dir` override would require a matching change here.

### [NOTE] `resolve_active_hub` stub location vs. gotcha wording
**Section:** § Technical context / Gotchas
**Issue:** The gotcha says "`cfg['hub_relative_path']` lives in `<hub>/.millhouse/config.local.yaml`." The proposed `resolve_active_hub` body reads from `wt / ".millhouse" / "config.local.yaml"` (the worktree *root's* stub, not the hub's full config). These are different paths when `hub_relative_path != "."`. The proposed code is correct per the stub-aware convention (worktree-root stub carries `hub_relative_path`; hub carries the full config), but the gotcha points to the hub path — a plan writer could implement the wrong read location.
**Fix:** Clarify: the worktree root's stub at `<wt>/.millhouse/config.local.yaml` holds `hub_relative_path` (that is what `resolve_active_hub` reads); the hub's full config at `<hub>/.millhouse/config.local.yaml` holds everything else.

## Verdict

APPROVE
Source-grounded verification confirms the problem statement, proposed helper bodies, scope, and test plan are all correct — proceed to plan writing.