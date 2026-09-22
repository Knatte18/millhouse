MILL_REVIEW_BEGIN
# Review: compute_baseline: use the task worktree's own pre-edit state, not a parent-branch checkout

```yaml
duration_s: 180.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-22
```

## Findings

### [NIT:consistency] Module-wide verdict cannot come from pair_cache
**Demoted-from:** BLOCKING
**Section:** Technical context "Helpers to reuse" vs. Decision `algorithm-simplification`
**Issue:** "Feed the module-wide command into the same pair list rather than running it separately" is incompatible with the module-wide algorithm decided above it: `compute_batch_baselines`/`_signatures_for_pair` return only signature lists and discard exit codes, and `_signatures_for_pair` returns `[]` for a non-zero exit that yields no extractable signature lines — so a collapsed run cannot distinguish `"clean"` from `"pre-existing-failures"`.
**Fix:** Decide one: keep the module-wide run separate with its own exit-code algorithm (losing the dedup), or state that `_signatures_for_pair`/`pair_cache` gain an exit-code component and how the verdict is derived from it.

### [BLOCKING:design] Corroboration deletion premise omits mid-task merge-in
**Section:** Decision `delete-corroboration` (and `merge-in-recompute`)
**Issue:** `_corroborate_batch_failure` runs its control at the batch's `start_sha`, which includes any parent content merged in mid-task by `mill-merge-in` — so it also waived failures introduced by a newly-merged red parent, not only "a failure introduced by an earlier batch of this same task". `--recompute-baseline` clears and refreshes only `module_verify_baseline`; each batch's `verify_baseline_failures` stays as captured before the merge, with no fallback once corroboration is gone.
**Fix:** State the disposition of per-batch baselines across a mid-task merge-in (recompute them, clear them, or accept strict gating) and correct the rationale's claim about what corroboration waived.

### [BLOCKING:design] Pre-edit precondition asserted, never enforced
**Section:** Problem / Decision `preflight-dirt-warning`
**Issue:** Correctness now rests on "at `--stage baseline` time the worktree is pre-edit", which is a runtime assumption with no guard; the only decided check is a post-hoc, never-blocking dirt warning for dirt the pre-flight itself creates. A capture taken against an already-modified tree caches `"pre-existing-failures"` — the direction `_verify_baseline`'s own docstring calls unsafe because it disables the regression gate for the rest of the task.
**Fix:** Decide whether the stage verifies the precondition before capturing (e.g. HEAD vs. merge-base and/or a clean-tree check, leaving the field unset when it fails) or explicitly accepts the risk with stated reasoning.

### [NIT:decision] `_run_verify_gates` start_sha disposition deferred
**Demoted-from:** BLOCKING
**Section:** Technical context, `_implementer_common.py` anchor
**Issue:** "`start_sha` ... may become unused at this call site — check its other readers before removing it from the signature" defers the decision to the implementer; `start_sha` is read inside `_run_verify_gates` only by the corroboration branch being deleted, and four call sites in `_implementer_common.py` pass it.
**Fix:** State outright whether the parameter is removed (and the four call sites updated) or retained as an accepted-but-ignored argument.

### [NIT:consistency] Timeout key comment still names baseline_prepare_cmd
**Section:** Scope, `mill-config.yaml` bullet
**Issue:** `baseline_verify_timeout_minutes`'s comment in both hub config and `plugins/mill/templates/mill-config.yaml` enumerates "(module-wide, per-batch, `baseline_prepare_cmd`)"; the scope deletes the key but says nothing about the surviving comment.
**Fix:** Note that the retained key's comment is rewritten alongside the deletion.

## Verdict

REQUEST_CHANGES
Module-wide verdict mechanics, merge-in staleness, and the pre-edit precondition are unresolved.
_Note: 2 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 2._
MILL_REVIEW_END
