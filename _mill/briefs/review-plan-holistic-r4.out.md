MILL_REVIEW_BEGIN
# Review: mill-merge-in/mill-finalize/codeguide-update: cleanup-ordering and path-resolution bugs — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [BLOCKING:design] Card 2 exposes dead-parent rebind to an absent status.md
**Location:** batch 1 / Card 2 (`mill-merge-in/SKILL.md` Entry step 2 rewrite)
**Issue:** Card 2 mandates the "Liveness check (#817)" paragraph run "in both branches" — including the new positional-`<branch>`-supplied branch that skips `resolve()`. In the exact #977 scenario this batch targets (closed-PR re-entry, `status.md` already removed by mill-finalize's cleanup), Card 1 makes `mill-merge` pass `parent_branch = cfg.git.base_branch` (its own status_path-absent fallback, never liveness-checked by `mill-merge` itself) to `mill-merge-in`. If that check now finds the branch dead, the imported dead-parent-rebind protocol calls `_status.update_field(status_path, "parent", resolved_branch)` against a `status_path` that does not exist — an unhandled write failure, i.e. exactly the class of crash #977 is fixing, reintroduced via a new path. Pre-plan this code was unreachable when `status.md` is absent, because `resolve()` itself raised before ever reaching the liveness-check paragraph; Card 2's rewrite is what newly makes it reachable in that state.
**Fix:** In Card 2, special-case (or explicitly except) the dead-parent rebind step when `status_path.exists()` is `False` — e.g. skip the rebind write and just proceed with the resolved/fallback branch (matching how `mill-merge`'s own Entry Step 4 already treats its status_path-absent fallback as exempt from the liveness-check/rebind machinery).

## Verdict

REQUEST_CHANGES
Card 2's liveness-check-in-both-branches rule can crash on a dead base branch when status.md is absent, re-triggering #977's failure class.
MILL_REVIEW_END
