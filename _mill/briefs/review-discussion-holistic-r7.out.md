MILL_REVIEW_BEGIN
# Review: compute_baseline: use the task worktree's own pre-edit state, not a parent-branch checkout

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-22
```

## Findings

### [BLOCKING:decision] compute_baseline's post-change signature unstated
**Section:** Scope (`_verify_baseline.py`) + Gotcha "`cwd_override` coordinate spaces"
**Issue:** Once the checkout is gone, `compute_baseline`'s `project_root`, `git_root` and `parent_branch` are all unread (no `.scratch/`, no rev-parse, no run-3 control in `project_root`), yet the discussion states a disposition only for `cwd_override_relative` and the return type — while it explicitly decides the analogous cases for `compute_batch_baselines`'s `project_root` and `_run_verify_gates`'s `start_sha`. It also leaves unstated whether the `_run_verify_gate`-mirroring cwd resolution happens caller-side or inside `compute_baseline`, and therefore what `cwd=None` means.
**Fix:** State the surviving parameter list for `compute_baseline`, and state that the caller resolves the absolute cwd (so the callee has no `git_root`/`project_root` fallback left to define).

### [BLOCKING:scope] merge-in's parent-branch resolution left with no disposition
**Section:** Scope (`millpy-merge-in-subagent.py`) + Decision `merge-in-recompute`
**Issue:** `_run_recompute_baseline` resolves the parent branch solely to feed `compute_baseline` (`millpy-merge-in-subagent.py:257-261`) and aborts the whole recompute with `baseline: "error"` when that fails; after an in-worktree recompute the resolve and its failure branch are dead, but the scope entry mentions only the asymmetric verdict and the batch clearing. The same call site passes the absolute `cwd_override` into `cwd_override_relative` today (`:266`), so its cwd handling must be restated once the parameter collapses to the absolute form.
**Fix:** Say whether the parent-branch resolve and its `"error"` early return are removed, and which cwd the merge-in recompute runs in when `verify:` is a plain string.

### [NIT:design] Guard and dirt-warning disagree across the two-invocation path
**Section:** Decisions `preflight-precondition-guard` + `preflight-dirt-warning`
**Issue:** `two-half-stage-ownership` makes two `--stage baseline` invocations the default path; a verify command that dirties a tracked file in invocation 1 is only warned about, but makes invocation 2's porcelain condition fail, so the whole per-batch capture is skipped and every batch gates strictly for the task with just a `result: "skipped"` line.
**Fix:** State that this interaction is accepted (it fails safe) or that the guard tolerates dirt attributable to a prior baseline invocation.

### [NIT:design] "Degrade to []" claim omits a malformed overview
**Section:** Gotcha "`--stage baseline` needs the plan, and may run before it exists"
**Issue:** The degrade-not-raise claim covers missing/unparseable *batch files* and carves out a missing `00-overview.md`, but `_plan_dag.extract_batch_index` raises `PlanDAGError` on a present overview with no/malformed `batches:` block — which would break the stage's stated "never raises, prints a JSON line" contract on the speculative path.
**Fix:** Extend the degrade-to-`[]` statement to cover `extract_batch_index`'s `PlanDAGError`.

### [NIT:consistency] List serialisation of the new scalar-block field unstated
**Section:** Decision `module-wide-verdict-source` / Scope (`_status.py`)
**Issue:** `module_verify_baseline_signatures:` is a list written "the same way as `module_verify_baseline:`", but that writer is `quote_scalar` (string-only), and the only list precedent in this file deliberately uses `yaml.safe_dump(..., default_flow_style=True)` rather than `str()` (`_status.py:689-696`) — a pitfall the code comments record.
**Fix:** Name the flow-sequence `safe_dump` form for the new field's value.

## Verdict

REQUEST_CHANGES
Two signature/call-site dispositions are unstated; the rest of the artefact verifies clean.
MILL_REVIEW_END
