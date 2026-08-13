MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-13
```

## Findings

### [BLOCKING:consistency] mill-merge-in's rebind reuses a status_path derivation batch 2 explicitly calls an anti-pattern
**Location:** `plugins/mill/skills/mill-merge-in/SKILL.md:17` vs `plugins/mill/skills/mill-merge/SKILL.md:111`
**Issue:** `mill-merge/SKILL.md`'s Entry Step 4 rebind explicitly warns "never a fresh `_paths.resolve_hub_path()` + literal `'_mill/status.md'` derivation, which walks from cwd instead of the already-resolved `worktree_root` and bypasses the config-driven `cfg['paths']['status_md']`". But `mill-merge-in/SKILL.md`'s Entry step 2 derives `status_path` exactly that way (`_paths.resolve_task_path(_paths.resolve_hub_path(), "_mill/status.md")`), and Card 7's new "Liveness check (#817)" paragraph reuses that same `status_path` for its rebind, while explicitly claiming to apply "the identical halt/report/confirm/rebind behavior" as batch 2's call site.
**Fix:** Either have Card 7 derive `status_path` via the config-driven `worktree_root`/`cfg['paths']['status_md']` path (matching mill-merge's corrected pattern) before rebinding, or explicitly document why mill-merge-in's existing literal-path derivation is safe here despite the warning batch 2 states for the identical operation.

## Verdict

REQUEST_CHANGES
Two call sites claim "identical" liveness-check/rebind behavior but diverge on status_path derivation, risking a wrong-path write in nested-hub layouts.
MILL_REVIEW_END
