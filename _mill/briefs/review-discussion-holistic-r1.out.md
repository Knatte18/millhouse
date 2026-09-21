MILL_REVIEW_BEGIN
# Review: mill-go/mill-merge-in orchestration robustness gaps, round 2

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-21
```

Twelve independent, individually-scoped Decisions, each with rationale and a rejected alternative. Cross-checked a broad, representative sample of the discussion's specific source claims directly against files in this worktree; every one held exactly as stated, with no fabrication or drift:

- `topo_order()` returns `list[str]` (confirmed signature + docstring); `iter_batch_verifies` at `_plan_dag.py` lines 618-631 matches the cited reference pattern (`extract_batch_index` -> `topo_order` -> `file_by_name` dict) verbatim, and `mill-merge-in/SKILL.md` line 148 does describe the exact dict-mismatch bug #1091 claims.
- `_FAILURE_MARKER_PREFIXES` values match exactly what #1060's rationale quotes; the on-demand baseline guard (`not batch_verify_baseline and replay_signatures and ...`) sits at line 1171 as claimed, confirming an empty `replay_signatures` list never triggers it.
- `mill-config.yaml`'s `merge.model: haiku` default confirmed; `sonnet` is a recognized tier alias (`_agent_dispatch.py`).
- `_forward_output`'s `card_ids: set[int] | None = None` default confirmed; neither `millpy-fix.py` nor `millpy-merge-in-subagent.py` reference `card_ids` anywhere, supporting #1104's "both callers never pass card_ids" claim.
- `_collect_task_intent`'s regex (`millpy-merge-in-subagent.py` line 93) matches `(Edits|Creates|Deletes)` only, confirming #1065's `Moves:` gap.
- `mill-go-base/SKILL.md` line 909's `PlanDAGError` handling escalates immediately with no renumber attempt, matching #1057's described current behavior exactly.
- `_check_verify_excludes_edited_tagged_test` registration call site at line 4533 matches #1069's cited location precisely.
- `_verify_baseline.py` exposes `compute_baseline`, `compute_batch_baselines`, `compute_batch_baseline_on_demand` as named in Technical Context.

No undecided items, no unresolved TBDs — the Q&A log closes every judgment call with a stated rationale. Scope in/out lists are explicit and leave no ambiguity a plan writer would need to resolve (e.g., #1057's and #1068's boundaries are drawn narrowly and explicitly). Each Decision states rationale and a rejected alternative. Testing section addresses every item, explicitly justifying the cases with no unit test (#1090, #1068, tier-bump/#1059/#1047) rather than leaving them silently uncovered. No repo `CONSTRAINTS.md` exists to cross-check against. No tooling/validator/`PYTHONPATH=` claims appear in this discussion (no `verify:` command proposed at this stage), so the CLAUDE.md cross-check criterion does not apply here.

## Verdict

APPROVE
Findings-free after source cross-checks; all twelve Decisions are grounded, scoped, and internally consistent.
MILL_REVIEW_END
