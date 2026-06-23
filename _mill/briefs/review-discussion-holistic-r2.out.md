MILL_REVIEW_BEGIN
# Review: Fix agent-dispatch cwd guard, implementer self-termination, and false-success contracts

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-23
```

The discussion is decision-complete across all five fixes. Each `### Decision:` carries rationale plus rejected alternatives; scope is crisply bounded with explicit Out items (no SendMessage loop, no language-specific test-superset, no fixer/merge tier change, no 2b-gate removal). The three round-1 gaps (raw commit-count derivation given start_sha predates the start-batch commit; param threading through both `_forward_output` and `finalize_from_output`; non-interactive `parent_branch` resolution) are now resolved in both the decision bodies and the Q&A log.

Verified against source: `_paths.resolve_hub_path` (153-219) is cwd-independent and honors `hub_relative_path`; `millpy-implement.py` anchors on `Path.cwd()` (102/129/130) and calls `finalize_from_output` (195) / `_forward_output` (308); `_implementer_common._forward_output` (311) and `finalize_from_output` (255) signatures match the threading plan; `_cleanliness.compute_terminal_dirt(worktree, task_dir, parent_branch)` (119) is read-only as claimed and distinct from `revert_out_of_scope_drift` (151) used by mill-go 2b; `millpy-fix.py` (120/146/147) and `millpy-review-code.py` (92-96, already uses `resolve_hub_path` only for `load_config`) match the described inconsistency; `_status.read_full` raises the raw `ValueError` (170/557/631); template `roles.implementer.model: haiku` (169) vs code default `sonnethigh` (147) confirms the template/code drift; `implementer-brief.md` has no anti-yield directive or porcelain self-check today; plan-batch.md cards are `### Card N:` (58); workflow `## Wiki mutations` paragraph (30-32) is a coherent insertion point.

Failure modes (incomplete batch, dirty in-scope tree, genuinely-missing status.md, no-operator finalize) and testing (per-fix unit tests with nested-hub/tempfile git fixtures; prose changes deferred to review) are addressed. Constraints (ASCII stdout, PYTHONPATH verify prefix, template/hub sync, subprocess-parity) are stated. No blocking ambiguity remains for a plan writer.

## Verdict

APPROVE
Decision-complete, all r1 gaps closed, claims verified against source.
MILL_REVIEW_END
