No stale `git_root`-based briefs_dir remains in either file — confirming the bug is fully fixed with no lingering old call sites. My holistic review is complete.

MILL_REVIEW_BEGIN
# Review: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-07
```

Verified all 8 batches (28 cards) against source. Every call site cross-checked directly:

- Batch 1: `_cleanliness.compute_scope_violations`/`clean_ephemeral_scope_violations` correctly rebased to `(hub_root, git_root)`; all 4 `_implementer_common.py` call sites and the `mill-go/SKILL.md` call site pass `git_root`; `test-cleanliness.py` has CV-1..9 and CESV-1..10 covering flat, nested, outside-subtree, and `git_root=None` cases.
- Batch 2: both `millpy-review-plan.py`/`millpy-review-code.py` briefs_dir now resolve under `project_root` (confirmed no stale `resolve_task_path(git_root, ...)` calls remain); nested-layout test cases added in both flow tests.
- Batch 3: `parse_verify_field` and 3-tuple `iter_batch_verifies` implemented exactly per the Shared Decision contract (fail-loud on malformed mapping); `test-plan-dag.py` covers all six contract cases.
- Batch 4: `cwd_override`/`module_wide_cwd_override` threaded through `_run_verify_gate`, `_run_verify_gates`, all 4 `_forward_output` call sites, and `finalize_from_output`'s pass-through; `_verify_baseline.compute_baseline`'s `cwd_override_relative` re-anchors both the verify subprocess and dependency junctions per Card 14; `millpy-implement.py`'s three read sites (per-batch x2, module-wide) and `_run_baseline_stage`'s one-liner collapse match Card 16 exactly. Tests cover precedence (#554 regression preserved) and nested-layout resolution.
- Batch 5: `millpy-fix.py`'s pre-initialization pattern, `_resolve_holistic_verify` mixed-cwd rejection, and all 4 read/thread sites match Cards 19-20 precisely; tests cover nested, uniform-holistic, mixed-cwd ValueError, and both `None`-regression paths.
- Batch 6: `_plan_validate.py`'s new/updated checks (`verify-not-isolated`, `verify-full-suite`, `verify-malformed-cwd`, `verify-mixed-cwd`) correctly avoid duplicate reporting on malformed mappings and cover overview-level verify; all 4 new test cases present.
- Batch 7: `mill-merge-in/SKILL.md` step 4 correctly unpacks the 3-tuple and resolves cwd (`hub_root` default, matching pre-batch-3 behavior); `test-merge.py` adds the nested verify-cwd integration case.
- Batch 8: `mill-plan/SKILL.md`, `plan-batch.md`, `plan-overview.md` all document the mapping form with matching guidance.

No out-of-plan files, no cross-batch contract violations, no duplicated verify-cwd logic outside `parse_verify_field`, no mutable-default or Windows-path-sep issues found. Flat-layout byte-identical behavior is preserved throughout (verified via `None`/no-cwd-override fallback chains and unchanged existing test assertions).

## Verdict

APPROVE
Implementation faithfully and consistently realizes every card across all 8 batches with thorough test coverage.
MILL_REVIEW_END
