MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: Phase Plan Review gate, convergence, and DAG-validation correctness bugs — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-21
```

## Findings

No findings. Verified end-to-end across all three batches:

- Batch 1 (Cards 1-7): step 4.5 -> 3.5 relocation is structurally correct in `mill-plan/SKILL.md`
  (sits after step 3, before Guardrail); the unconditional round-recorded append paragraph is
  inserted correctly; 4a's and 4d's now-redundant `append_phase(plan-review-r{N}...)` calls are
  removed exactly once each; the tree-guard citation paragraph is updated to list 3.5/4b/4c/4d
  (4a correctly dropped); `mill-go-base/SKILL.md`'s cross-reference at line 801 correctly reads
  "step 3.5". Card 2's four dispatch-site `plan_skip_checks` threading clauses are all present
  (step 2 agent/subprocess, step 3.5 agent/subprocess) plus the Phase: Plan persist paragraph and
  Phase: Plan Review read-back paragraph. Card 3's explicit `_plan_dag.validate` call shape is
  present verbatim at both 4b and 4d. Card 4's Principles bullet is correctly positioned. Card 5's
  convergence-gate formula, heading rename, and all four
  `" (min_rounds not satisfied by round cap)"` occurrences are correctly applied — grepped and
  confirmed zero stray `min_rounds/demoted-predicate` or `step 4.5` references remain. Card 6's
  `out-of-worktree-target` paragraph and fix-table row are both present and correctly placed. Card
  7's Done-gate reminder and `mill-config.yaml` template comment both match.
- Batch 2 (Cards 8-10): `_check_cross_batch_creates_no_depends_on` mirrors
  `_check_parallel_modifies_overlap`'s shape exactly, reuses `_compute_transitive_ancestors`, is
  wired into `run()` right after the overlap check, and the docstrings (module + function) are
  updated. `_is_python_project` is correctly extracted as a shared helper and reused by both
  `_check_verify_not_isolated` and `_check_verify_full_suite` (no duplication). The widened
  `verify-full-suite` check's four branches (run-all.py, `go test ./...`, `dotnet test`, bare
  pytest gated on `_is_python_project`) match the specified regexes/logic exactly, evaluated in
  the specified order, returning only the first match. `_check_non_existent_path`'s
  Context:/Edits:+Creates: split correctly uses `resolve_ref_paths(..., soft_fail_gitignored=True)`
  for Context: only, with the exact call shape given in the card. All new test functions (Card 8:
  clean/dirty/transitive-clean; Card 9: Go/C#/pytest fixtures with Python-marker gating; Card 10:
  gitignored-clean/not-ignored-dirty/edits-still-dirty) exist and are registered in `main()`'s
  `tests = [...]` list — none are orphaned/dead code.
- Batch 3 (Card 11): both Step 1.5 fix-table row edits (`cross-batch-creates-no-depends-on` new
  row, `non-existent-path` row's spliced sentence) are present and correctly worded, documenting
  Batch 2's checks without touching the `out-of-worktree-target` row Batch 1 owns (no overlap).

Cross-batch contracts hold: Batch 3's depends-on [1, 2] is honored (no `parallel-modifies-overlap`
between batches; fix-table rows added by Batch 3 describe checks Batch 2 actually implements).
`All Files Touched` in the overview matches the five files actually edited.

## Verdict

APPROVE
All three batches faithfully implement their cards; no cross-batch contract or duplication issues found.
MILL_REVIEW_END
