MILL_REVIEW_BEGIN
# Review: compute_baseline: use the task worktree's own pre-edit state, not a parent-branch checkout

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-22
```

## Findings

### [BLOCKING:design] §0.55 done-gate pre-flight dirties the tree first
**Section:** Decision `preflight-precondition-guard` / Scope "Out" (`done_gate_baseline_preflight`)
**Issue:** `mill-go-base/SKILL.md:539-548` runs `_done_gate.run_preflight` (arbitrary `done_gate` command, `cwd=git_root`, `_done_gate.py:115-117`) immediately *before* §0.5, and line 574 states its purpose is letting "a self-capturing regression/snapshot suite" capture its baseline into the tree — i.e. tracked-file writes outside `_mill/`/`.millhouse/` are the intended behaviour, which makes the guard's porcelain condition (2) fail and silently skips the entire capture task-wide for every hub with `done_gate_baseline_preflight: true`.
**Fix:** State the disposition — either the guard's exclusion set accounts for §0.55's writes, or the discussion records that this config combination deliberately disables the capture and says so in the `result: "skipped"` reason.

### [BLOCKING:decision] Guard's `<parent>` input has no source or error path
**Section:** Decision `preflight-precondition-guard`; Gotcha "`compute_baseline`'s surviving signature"
**Issue:** The guard needs `merge-base HEAD <parent>`, but the discussion never says where `--stage baseline` obtains `<parent>` nor what happens when resolution fails, while simultaneously asserting `parent_branch` has "nothing to resolve"; `_run_module_wide_standalone`'s existing `_parent_branch.resolve` + `{"result": "error"}` early return (`millpy-implement.py:150-154`) is listed as a key anchor with no disposition, even though the analogous merge-in block at `:257-261` is explicitly dispositioned as removed.
**Fix:** State whether that resolve block is retained (repointed at the guard) or replaced, and that an unresolvable parent or a non-zero `merge-base` skips the capture rather than proceeding unguarded.

### [NIT:design] Enumeration degrade list omits `parse_verify_field`'s ValueError
**Section:** Gotcha "`--stage baseline` needs the plan, and may run before it exists"
**Issue:** The stated degrade conditions cover a missing/unparseable batch file and `extract_batch_index`'s `PlanDAGError`, but `parse_verify_field` raises `ValueError` on a well-formed-YAML malformed `verify:` mapping (`_plan_dag.py:483,490,491`), which would break the "never raises, prints a JSON line" contract on the unwatched speculative path.
**Fix:** Note that `verify-malformed-cwd` (`_plan_validate.py:3877`) covers this upstream, or add the ValueError to the degrade list.

### [NIT:consistency] "leaves every baseline field unset" is wrong on invocation 2
**Section:** Decision `preflight-precondition-guard`
**Issue:** On the default two-invocation path the §0.5 invocation may find `module_verify_baseline` already written by the speculative invocation, so "leaving every baseline field unset" could be read as an instruction to clear it.
**Fix:** Say the skip writes no field and clears none.

### [NIT:scope] Per-batch JSON line's result vocabulary undefined
**Section:** Decision `two-half-stage-ownership`; Gotcha "The stage's JSON output shape is consumed by SKILL.md prose"
**Issue:** Only `"deferred"` is named for the `substage: "per_batch"` line, while the module-wide line has a pinned `computed|cached|error|skipped` set that §0.5 branches on (`SKILL.md:605`).
**Fix:** Enumerate the per-batch `result` values the SKILL.md edit must describe.

## Verdict

REQUEST_CHANGES
Guard's parent input and its collision with the §0.55 done-gate pre-flight are unresolved.
MILL_REVIEW_END
