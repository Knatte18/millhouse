MILL_REVIEW_BEGIN
# Review: compute_baseline: use the task worktree's own pre-edit state, not a parent-branch checkout

```yaml
duration_s: 200.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-22
```

## Findings

### [BLOCKING:design] Signature list can serialise across multiple lines
**Section:** Decision `module-wide-verdict-source` / Scope `_status.py`
**Issue:** `yaml.safe_dump(..., default_flow_style=True)` wraps at PyYAML's 80-column `best_width`, so two realistic failure signatures emit as 2+ physical lines; the prescribed accessors mirror `set_module_verify_baseline`/`clear_module_verify_baseline`, which are strictly single-line (`_status.py:383-385` regex rewrite-in-place, `:426` `del lines[i]`) — a clear or a re-set would strand continuation lines, and `read()` `yaml.safe_load`s the whole top block (`:204`), so every subsequent `_status` read raises for the rest of the task.
**Fix:** State that the value must serialise to exactly one physical line (e.g. `yaml.safe_dump(..., default_flow_style=True, width=10**9)` or `json.dumps`), or that the new accessors handle a multi-line value explicitly.

### [NIT:decision] `git_name`/`git_email` left with no stated disposition
**Demoted-from:** BLOCKING
**Section:** Decision `start-sha-parameter` / Scope `_implementer_common.py`
**Issue:** `git_name`/`git_email` exist in `_implementer_common.py` solely to drive the two persist-commits this task deletes (`:1208-1222`, `:1270-1284`) — after the change they are dead through `_run_verify_gates` (`:1055-1056`), `_forward_output` (`:1903-1904`), `finalize_from_output` (`:1739-1740`) and both CLI call sites (`millpy-fix.py:490`, `millpy-implement.py`), plus three docstring passages (`:1146-1151`, `:1798-1801`, `:1969`) that justify them by the deleted feature; `status_path`/`batch_name` are likewise unread inside `_run_verify_gates` once the prelude and corroboration go.
**Fix:** Extend `start-sha-parameter` (or add a decision) stating whether those four parameters are removed or retained, since its own rationale about dead forwarding chains applies to them verbatim.

### [NIT:consistency] Guard's skip payload carries no `substage` key
**Demoted-from:** BLOCKING
**Section:** Decision `preflight-precondition-guard` vs `two-half-stage-ownership`
**Issue:** The guard prints `{"stage": "baseline", "result": "skipped", "reason": "worktree is not pre-edit"}` with no `substage`, while `two-half-stage-ownership` pins a per-batch `skipped` result meaning "`preflight-precondition-guard` refused" and requires both §0.5 sites to select the JSON line **by `substage`** — an untagged line matches neither selector, and the existing payload builder already tags every module-wide line (`millpy-implement.py:112-122`).
**Fix:** Specify whether the guard emits one untagged line or one tagged line per half, and reconcile it with the substage-selection contract the SKILL.md edit depends on.

### [BLOCKING:design] Batch clearing unreachable when no module-wide verify exists
**Section:** Decision `merge-in-batch-baseline-staleness`
**Issue:** The clearing is placed "alongside the `module_verify_baseline` reset it already performs" (`millpy-merge-in-subagent.py:255`), but `:242-252` returns early with `baseline: "skipped"` whenever `module_wide_verify_cmd is None` — so a task with per-batch `verify:` commands but no overview-level one keeps every stale pre-merge `verify_baseline_failures`, the exact unsafe-direction waiver the decision exists to remove; the same applies to the `:224-228` and `:234-240` error returns.
**Fix:** State where the unconditional batch clearing runs relative to those early returns (per-batch staleness is independent of whether a module-wide verify is configured).

## Verdict

REQUEST_CHANGES
Four decisions are underspecified in ways that change behaviour or brick status.md.
_Note: 2 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 2._
MILL_REVIEW_END
