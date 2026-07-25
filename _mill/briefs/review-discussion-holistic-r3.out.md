MILL_REVIEW_BEGIN
# Review: Batch review/verify pipeline doesn't account for cross-batch state changes

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

Verified against source: `_review_code.py:279` (`_, moves_targets_union = compute_moves_union(plan_dir)`), `_review_common.py:714-736` (`compute_moves_union` docstring — sources/targets semantics, and confirms Decision 1's rationale correction that the docstring's next sentence covers targets/`creates_union`, not sources), `_review_common.py:755-800` (`resolve_ref_paths` docstring/hard-fail path matches #686 mechanism), `_review_plan.py:354,668,394,490,780-781,842` (both halves kept, out-of-scope claim holds), `_plan_dag.py:359-416` (`iter_batch_verifies` current signature/body matches exactly, no `status_path` yet), `millpy-fix.py:225,332-336,452-456` (`status_path` already in scope at both call sites, `_resolve_holistic_verify` unchanged), `_status.py:540-547,667-687,945` (`_BATCH_STATES`, `read_batches` raising `ValueError` on malformed fence, `"name"`/`"state"` dict keys, `init_batches`), `_plan_validate.py:43-53,220-241` (`_plan_validate` imports `_plan_dag`, confirming the circular-import rejection rationale; `_parse_deletes_only` logic mirrors `compute_deletes_union`'s inline logic almost verbatim, supporting the extraction claim), `mill-merge-in/SKILL.md:91-134` (Step 4 heading/content and existing `skip_list`/`skipped`/report-line pattern match exactly). No fabricated or inaccurate claims found.

Round 3 finds no new gaps. Prior rounds' corrections (parse_deletes non-existence in r2, status_path/Decision-2 composition and reason-attribution mechanism in r1, multi-target/coordinate-space limitations and their locking tests in r2) all hold up against source and are internally consistent with each other and with the Testing section's fixtures.

## Verdict

APPROVE
All technical claims verified against source; no undecided items, scope ambiguity, or unaddressed failure modes remain.
MILL_REVIEW_END
