MILL_REVIEW_BEGIN
# Review: mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] check_and_restore has no path to status.md for the audit record
**Section:** Scope (In) bullet 4; Decision "Detection behavior: record, don't block"; Testing "Record shape"
**Issue:** `check_and_restore(worktree, tracked_root="_mill", *, record=True)` carries no `status_path`/`cfg` parameter, yet `record=True` is specified to drive a `status.md` audit-append via `append_recovery_log(status_path, ...)`, and the Testing section ties `record` directly to "whether the status.md audit-append side effect happens" — implying `check_and_restore` itself performs the call. Nothing says how it locates `status.md`: hardcode `<worktree>/<tracked_root>/status.md` (bypassing the project's normal config-driven `cfg['paths']['status_md']` resolution) or thread an undocumented extra parameter.
**Fix:** State explicitly whether `check_and_restore` takes an additional `status_path` (or `cfg`) argument, or deliberately hardcodes the `<tracked_root>/status.md` convention as a named exception (the doc already models this pattern elsewhere for the cleanliness-snapshot literal-path case).

### [GAP] worktree parameter binding is ambiguous between git root and hub root
**Section:** Technical context, "Config/path resolution" bullet
**Issue:** States `worktree` "resolves via `_paths.resolve_git_root()` / `_paths.resolve_hub_path()`" without saying which one to pass. `tracked_root="_mill"` is a bare relative pathspec, so `git -C <worktree> status --porcelain -- _mill` only finds real content when `worktree` is the hub anchor (each skill's own `worktree_root`, bound via `resolve_hub_path()` for mill-start/mill-plan or `resolve_active_hub()` for mill-go — the latter never mentioned here at all) rather than `git_root`. These two differ precisely in nested-hub layouts, which is the exact layout the original incident (#726) occurred in per the Problem section; passing `git_root` would make the new safeguard a silent no-op in that same layout.
**Fix:** State explicitly that `check_and_restore`'s `worktree` argument must be each skill's already-bound hub-anchor local (`worktree_root`), never `git_root`, and name `resolve_active_hub()` alongside `resolve_hub_path()` for mill-go.

## Verdict

GAPS_FOUND
Two unresolved data-flow/path-binding gaps in check_and_restore's design remain; everything else checks out against source.
MILL_REVIEW_END
