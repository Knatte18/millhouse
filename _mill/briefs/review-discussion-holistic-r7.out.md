MILL_REVIEW_BEGIN
# Review: Improve diagnosability of plan-validate errors and finalize verify-replay failures

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (per company/model-string; cannot self-verify beyond training)
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] Shared checkout's single dependency-junction call ignores per-batch cwd variance
**Section:** Decisions `gap2-shared-transient-checkout` / `gap2-checkout-teardown-extraction`
**Issue:** `_plan_dag.parse_verify_field` lets EACH batch's own `verify:` frontmatter independently resolve to `cwd: hub`, `cwd: git_root`, or the plain-string default (confirmed at `millpy-implement.py:436-438`, `_implementer_common.py:741-745`), so a single plan can mix batches whose effective verify cwd differs from each other and from the module-wide command's. `compute_baseline`'s existing junction loop links `.venv`/`node_modules`/etc. at exactly one `effective_tmp_path` per invocation (`_verify_baseline.py:180-193`); the new design has `_run_baseline_stage` call `_link_dependency_dirs` (a helper taking one `target_path`) exactly ONCE for the whole shared checkout, then reuses that single linked path for the module-wide command AND every batch's command via the new `(name, command, cwd)`-triple function.
**Fix:** Either link dependency dirs at every distinct cwd-resolution actually present among the module-wide command and all enumerated batches for this task (a set, not a single path), or explicitly scope this task to plans where all verify commands share one cwd and state that as an accepted limitation/out-of-scope item.

## Verdict

GAPS_FOUND
One unaddressed feasibility gap in the shared-checkout dependency-junction design for mixed-cwd batches.
MILL_REVIEW_END
