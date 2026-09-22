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

### [BLOCKING:design] Speculative launch runs before `## Batches` exists
**Section:** `eager-not-lazy` / Gotcha "`--stage baseline` needs the plan"
**Issue:** The speculative early launch fires in `mill-go-base/SKILL.md`'s entry-gate wait (line 197-206), which precedes `## Prepare`'s `_status.init_batches` (line 239); `_status.set_batch_field` raises `ValueError: Batch <name> not present in ## Batches` (`_status.py:1092`) when the section is absent, so every per-batch write in that path fails after paying the suite runs — and §0.5 (line 583) says the speculative run "IS the complete baseline computation", so nothing recaptures them.
**Fix:** State how the eager per-batch capture persists when `## Batches` does not yet exist (seed it, defer the batch half, or have §0.5 re-invoke the stage) and which of the two launch paths owns that.

### [BLOCKING:design] `iter_batch_verifies` drops batches the gate still runs
**Section:** Helpers to reuse — `iter_batch_verifies(..., status_path=None)`
**Issue:** With `status_path=None`, reason 2 suppression is at its broadest (`_plan_dag.py:672-681`: every strictly-later batch counts as a remover), yet the per-batch gate resolves `verify_cmd` straight from the batch frontmatter (`millpy-implement.py:547`, `:819`) and never applies that filter — so a batch whose verify references a path a later batch deletes gates with no baseline. The discussion asserts both filters are "correct for a baseline capture" without addressing that divergence.
**Fix:** Decide explicitly whether the capture set must equal the gate set (raw per-batch enumeration) or accept strict gating for reason-2-suppressed batches, and say why.

### [NIT:consistency] `pair_cache` seeding is not run-schedule-identical
**Section:** `module-wide-verdict-source`
**Issue:** `_signatures_for_pair` skips run 2 only when run 1 exits 0 **and** extracted zero signatures (`_verify_baseline.py:554`); the module-wide algorithm returns "clean" after one run on any zero exit, so a green run that still emits an extractable failure line seeds a one-run signature set where the pair path would have unioned two. The "faithful rather than approximate" claim is therefore overstated (the divergence errs toward stricter gating).
**Fix:** Narrow the claim to "identical except when a zero-exit run yields signatures" and state that the seeded set is accepted as possibly narrower.

### [NIT:consistency] Post-merge-in recapture escape hatch is unreachable
**Section:** `merge-in-batch-baseline-staleness`
**Issue:** "unless a later `--stage baseline` invocation finds the precondition satisfied" cannot occur — §0.5 invokes the stage only for the task's first batch, and after a mid-task merge-in the worktree is never pre-edit again, so `preflight-precondition-guard` would refuse anyway.
**Fix:** Drop the clause and state plainly that batch gates are strict for the remainder of the task after a merge-in.

### [NIT:consistency] "Missing plan returns 0" contradicts the entry path
**Section:** Testing — `test-millpy-implement.py`
**Issue:** "Missing/unparseable plan -> stage prints a JSON line and returns 0" does not hold for a missing `00-overview.md`: `millpy-implement.py:458-460` prints to stderr and returns 1 before the `--stage baseline` branch is ever reached.
**Fix:** Scope the claim to missing/unparseable *batch* files, where `iter_batch_verifies` genuinely degrades to `[]`.

## Verdict

REQUEST_CHANGES
Two unresolved design gaps: speculative-launch batch persistence, and capture-set vs gate-set divergence.
MILL_REVIEW_END
