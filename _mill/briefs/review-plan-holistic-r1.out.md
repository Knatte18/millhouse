MILL_REVIEW_BEGIN
# Review: compute_baseline: use the task worktree's own pre-edit state, not a parent-branch checkout — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-23
```

## Findings

### [BLOCKING:design] No shared source for the hub-fragment exclusion prefixes
**Location:** batch 3 / Cards 11, 12, 13, 14
**Issue:** Card 11's `_baseline_preflight_skip_reason` computes the `{"_mill/", ".millhouse/"}` exclusion set re-anchored via `project_root.relative_to(git_root)` entirely inline, with no exposed helper. Card 12's `_warn_new_dirt(before, after, exclusions)` requires the identical tuple as a caller-supplied argument, but Cards 13 and 14 (the two callers wrapping their halves in Card 12's snapshot) never say how to obtain `exclusions` — each must independently re-derive `project_root.relative_to(git_root)` prepended to the two prefixes, duplicating Card 11's logic at 3+ call sites with no single source of truth.
**Fix:** Add a small shared helper (e.g. `_baseline_exclusion_prefixes(project_root, git_root) -> tuple[str, str]`) that both Card 11's guard and Card 12's callers invoke, so the batch's own stated invariant ("the two checks cannot drift apart") is actually enforced by the code shape, not just asserted in prose.

### [BLOCKING:design] Batch 5's dependency rationale is factually wrong about millpy-merge-in-subagent.py
**Location:** batch 5 (`05-merge-in-baseline-recompute.md`) Batch Scope paragraph
**Issue:** The batch justifies depending only on batch 2 (not batch 4) with: "`millpy-merge-in-subagent.py` never calls `_run_verify_gates`/`_forward_output`/`finalize_from_output`." This is false — verified in `plugins/mill/scripts/millpy-merge-in-subagent.py`: `_run_conflicts` calls `_forward_output(output, project_root, commit_sha_field_name="pre_merge_head")` and the conflicts-mode finalize branch calls `finalize_from_output(Path(args.agent_output), project_root, start_sha=None, snapshot_path=None, session_id=None, commit_sha_field_name="pre_merge_head")`, both of which transitively invoke `_run_verify_gates`.
**Fix:** Correct the rationale: the no-batch-4-dependency conclusion still holds, but because neither call site ever passes `batch_name`/`git_name`/`git_email` (they rely on the removed parameters' defaults being `None`), not because the file "never calls" these functions.

### [BLOCKING:consistency] Card 34 misattributes the quoted claim's location in mill-go-base/SKILL.md
**Location:** batch 7 / Card 34 (`07-skill-docs-baseline.md`)
**Issue:** Card 34 instructs narrowing the claim "the speculative early launch's single module-wide result IS the complete baseline computation for this batch, with nothing further to run" inside "the Entry-gate wait for upstream mill-plan section's speculative-launch bullet," and changing that branch's handling "from 'leave the file as-is... nothing further to run' to: ...". Verified against `plugins/mill/skills/mill-go-base/SKILL.md`: "nothing further to run" appears only at line 583, inside the separate "0.5. Baseline pre-flight" section, not inside "Entry-gate wait for upstream mill-plan" (whose own "leave the file as-is" text, at line 199, never contains "nothing further to run" — it is about not double-launching the background job). The quoted combined phrase does not exist as written anywhere in the file.
**Fix:** Split Card 34 into two accurately-located edits: (1) in "0.5. Baseline pre-flight," narrow/replace the "nothing further to run" claim at its actual line; (2) separately state what (if anything) changes in the "Entry-gate wait" section's "exit"/"leave the file as-is" branch, since today that branch does no baseline-completeness claim of its own.

### [NIT:consistency] Preflight guard is called twice per invocation, not once as documented
**Location:** batch 3 / Card 11 vs. Cards 13, 14
**Issue:** Card 11's docstring states `_baseline_preflight_skip_reason` is "a pure gate, called once per `--stage baseline` invocation, before either half attempts anything." But Card 13's module-wide half and Card 14's per-batch half (step 2) each independently call it, so a single `--stage baseline` invocation can run the guard's `git merge-base`/`git diff --name-only` pair twice.
**Fix:** Either resolve the skip reason once in `_run_baseline_stage` and thread it to both halves, or correct Card 11's docstring to describe the "called once per half, up to twice per invocation" reality.

## Verdict

REQUEST_CHANGES
Two design gaps (unshared exclusion-prefix logic, a false dependency-rationale claim) and a misattributed doc-edit location need fixing before implementation.
MILL_REVIEW_END
