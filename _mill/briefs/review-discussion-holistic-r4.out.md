MILL_REVIEW_BEGIN
# Review: mill-go's one-shot pre-batch-1 baseline can't cover a task's own later per-batch-baseline capability

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4-5
reviewed_file: _mill/discussion.md
date: 2026-08-05
```

Verified against source: `millpy-implement.py` (`_run_baseline_stage` ~L220, `_enumerate_batch_verify_triples` ~L179 incl. its `verify: None`-skip at L214-216, `--stage baseline` dispatch L663-666, finalize's `verify_baseline_failures` read L730, Agent-mode-only path; "Stage: full" branch L966 with its own `_status.read_batches`/`verify_baseline_failures` lookup L1010-1018), `mill-go/SKILL.md` (0.5 pre-flight §396-408, shared "## Agent-mode dispatch" step 6 §301-307 confirmed reused verbatim across implement/review/fix call sites, `### 1. Implement`'s Agent-mode vs subprocess/psmux branches §410-437 confirming the bare/`--stage full`-default form, 0.55 done-gate pre-flight §370 confirmed as the distinct unrelated mechanism, repeated per-call-site tree-guard-checkpoint precedent confirmed at 9+ sites), `_paths.py` (no pre-existing `is_self_hosting_task`), `_status.py` (`read_batches`/`set_batch_field`/`get_module_verify_baseline` all present), `_plan_dag.parse_verify_field` (docstring confirms `None`-command semantics), `_verify_baseline.py` (`_checkout_parent_branch`, `_link_dependency_dirs`, `compute_baseline`, "never raises" comment at L116).

All technical-context claims (function names, line numbers, dispatch-mode asymmetry, trigger-condition edge case, hook-placement uniqueness) check out exactly against current source. No fabricated or stale claims found. Rounds 1-3 GAPs (hook-placement mode-specificity, no-verify-batch trigger misfire, hook-placement call-site uniqueness) remain correctly fixed and are consistent with the source read in this round.

## Verdict

APPROVE
All claims verified against source; no new gaps found; prior rounds' fixes hold up.
MILL_REVIEW_END
