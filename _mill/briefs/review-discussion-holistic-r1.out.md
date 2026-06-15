I have enough verification. Let me check one more thing: the discussion claims `_review_plan.prepare/run` already pass `git_root` into `resolve_ref_paths` and the holistic prepare path. This is confirmed at lines 327-339. 

Now I have a clear picture. Let me note a few observations for the review:

1. The discussion is well-grounded and matches source. Key claims verified accurate.

2. **resolve_existing_paths asymmetry**: The discussion (line 180-182) says apply "the same reorder" to `resolve_existing_paths`. But the current `resolve_existing_paths` git_root fallback (line 722-726) only tries `git_root / raw`, NOT `git_root / root / raw`. So for `resolve_existing_paths` the fix is not merely a "reorder" — a `git_root / root / raw` candidate must be ADDED (it doesn't exist today). The discussion's Testing section (line 228) requires `_check_*` to resolve `git_root/root/raw`, which is exactly what `resolve_existing_paths` feeds. This is a subtle scope point worth flagging so the plan writer adds the candidate rather than just reordering.

Let me verify there's no `git_root/root/raw` in resolve_existing_paths — confirmed at lines 721-726 it only has `git_root / raw`.

Let me check the `_review_plan.run` signature briefly to confirm prepare doesn't currently take plan_dir param that the validator would need — actually the validator gate is added in the CLI prepare branch, not in `_review_plan.prepare`. The CLI prepare branch (lines 124-150) has `cfg`, `slug`, `project_root`, `git_root`, `wiki_root` available — it can call `resolve_path(cfg["paths"]["plan_dir"], slug)` itself. Good, feasible.

I have enough to produce the review.

MILL_REVIEW_BEGIN
# Review: Fix millpy-review-plan validator gaps and resolve_ref_paths path-doubling

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-15
```

## Findings

### [GAP] resolve_existing_paths needs added candidate, not just reorder
**Section:** Scope (bullet 3) / Technical context (`_review_common.py`, ~L180-182)
**Issue:** Discussion says apply "the same reorder" to `resolve_existing_paths`, but its current git_root fallback (`_review_common.py:721-726`) only tries `git_root / raw` — there is no `git_root / root / raw` candidate to reorder; it must be ADDED. Without it, the #471 layout (cwd==git_root/root) still doubles `root` and the validator's `_check_non_existent_path`/`_check_batch_oversized` (which feed through `resolve_existing_paths`) will not find files at `git_root/root/raw` — defeating the threaded `git_root` in the #466 fix.
**Fix:** State explicitly that `resolve_existing_paths` gains a new primary `git_root / root / raw` candidate (mirroring `resolve_ref_paths:656`), not a reordering of existing ones.

### [NOTE] prepare-stage validator wiring (plan_dir/root) not spelled out
**Section:** Decisions #465 / Technical context (`millpy-review-plan.py` ~L124-150)
**Issue:** The decision says run `_plan_validate` in the `--stage prepare` branch, but unlike `--stage full` that branch never computes `plan_dir` or the overview `root`. The plan writer must add `plan_dir = resolve_path(...)` and pass `git_root` + `root` into the prepare-branch validator call to satisfy the #466 base-consistency fix in the agent path too.
**Fix:** Note that the prepare branch must construct `plan_dir`/`git_root`/`root` for the gate (full branch is the template; prepare currently has none of these).

## Verdict

GAPS_FOUND
The resolve_existing_paths step is an add, not a reorder; clarify before planning.
MILL_REVIEW_END