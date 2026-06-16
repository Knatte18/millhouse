MILL_REVIEW_BEGIN
# Review: Fix nested mill layout paths, whole-repo formatter drift, and stacked-branch PR cleanup

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-16
```

## Findings

### [NOTE] PR-base var swap in mill-finalize Step 5 not spelled out
**Section:** stacked-pr-path / Technical context (Stacked PR)
**Issue:** Decision says "the PR targets `parent_branch`", but the existing mill-finalize Step 5 literally invokes `/git-pr <base_branch>` (SKILL.md:94); the plan must replace that token, not just the trigger clause at line 31.
**Fix:** Have the plan note both edits explicitly — drop the `parent == base` clause AND change the Step 5 invocation arg from `<base_branch>` to `<parent_branch>`.

### [NOTE] plan-CLI line-119 `find_active_slug` already uses project_root
**Section:** review-plan-anchor
**Issue:** Discussion frames the plan-CLI fix as switching `Path.cwd()` (line 102) to `resolve_hub_path()`; line 119 already passes `project_root` (not `git_root`), so it auto-corrects once line 102 changes — no separate edit, unlike the discussion CLI's line-88.
**Fix:** None required; confirm the plan does not redundantly "move line 119" as if it were on `git_root` like the discussion CLI.

## Verdict

APPROVE
All decisions grounded, both r1 GAPs resolved, scope and testing concrete; two NOTEs only.
MILL_REVIEW_END
