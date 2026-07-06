All discussion claims verified accurately against source: `_cleanliness.py` (line 59 `compute_scope_violations(worktree)`, line 210 signature, line 256 `_is_go_main_artifact`, line 268 join), the identical buggy `briefs_dir = resolve_task_path(git_root, ...)` in both review CLIs (plan 151-153, code 150-152), `_run_verify_gate` cwd selection at `_implementer_common.py:580`, `iter_batch_verifies` returning 2-tuples (`_plan_dag.py:285`, string-only handling at 320-321), and all `verify` read sites in `millpy-implement.py` (311/371/591) and `millpy-fix.py` (239/242/244/284). The discussion's technical grounding is precise.

MILL_REVIEW_BEGIN
# Review: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-06
```

## Findings

### [NOTE] parse_verify_field behavior for absent/null verify unspecified
**Section:** Decisions § Verify-cwd explicit field / Testing § parse_verify_field
**Issue:** `iter_batch_verifies` must keep skipping pure-docs batches (current `_plan_dag.py:320` only appends when `isinstance(verify,str) and verify.strip()`), but the 5 listed `parse_verify_field` test cases omit the "verify key absent / null" case, and the return contract for that input is not stated.
**Fix:** State that `parse_verify_field` returns `(None, None)` for missing/empty verify and add a test case, so `iter_batch_verifies`' skip semantics are preserved unambiguously.

### [NOTE] Who derives cwd_override_relative for compute_baseline is implicit
**Section:** Decisions § Verify-cwd explicit field (baseline paragraph)
**Issue:** `parse_verify_field` returns a resolved absolute Path (`hub_root`/`git_root`), but `compute_baseline` needs the hub-relative *prefix* (`tmp_path / <prefix>`); the discussion adds the parameter without saying the caller computes it via `hub_root.relative_to(git_root)`.
**Fix:** Note that the baseline caller derives the relative prefix from the resolved cwd before passing it, so the plan writer wires the conversion rather than re-resolving.

## Verdict

APPROVE
Zero blocking gaps; scope, decisions, and per-file test strategy are complete and source-accurate.
MILL_REVIEW_END