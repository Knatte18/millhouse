# Plan: millpy-review-plan: verdict/envelope disagreement and reviewer_model mis-recording

```yaml
task: 'millpy-review-plan: verdict/envelope disagreement and reviewer_model mis-recording'
slug: 'review-plan-verdict-envelope-model-bugs'
approved: false
started: '20260904-081054'
parent: 'main'
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: mechanism-claim-rule
    file: 01-mechanism-claim-rule.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-templates.py
```

## Shared Decisions

### Decision: bugs A and B are already fixed -- no code changes for them

- **Decision:** this plan makes no change to `_review_common.py`'s `apply_actual_model_override` / `finalize_scope` verdict logic, and adds no new test coverage for the `reviewer_model` mis-recording bug (#963/#922) or the verdict/envelope-mismatch bug (#924/#912/#910).
- **Rationale:** both are already fixed on this branch's base (`main`) -- `apply_actual_model_override` plus the `--actual-model` finalize flag (issue #644, commits `feeab63e`..`82f4d80e`) fixes the reviewer_model bug; `finalize_scope`'s `demoted_any`-gated verdict-preservation logic (commit `12916293`) fixes the verdict/envelope-mismatch bug, and is covered by passing tests `test_verdict_preserved_when_reviewer_writes_request_changes_with_zero_blocking` and `test_verdict_preserved_for_plan_and_code_types` in `test-review-class-taxonomy.py`. See `_mill/discussion.md`'s Problem section and the `bugs-a-b-already-fixed` Decision for the full verification trail.
- **Applies to:** all batches (there is only one batch in this plan, but this decision scopes the whole task -- do not "helpfully" re-touch this logic).

### Decision: mechanism-claim rule scope, placement, and enforcement

- **Decision:** the new mechanism-claim source-verification rule (fixing #949) is added ONLY to `review-plan-holistic.md` and `review-plan-batch.md`, as a new paragraph appended to each template's existing `## Source-grounding rule` section (not a new `## Criteria` bullet), and is prompt-only discipline (no schema/parser change, no structured `**Verified:**` finding field).
- **Rationale:** matches #949's explicit ask (plan-review templates only -- code review already grounds against real diffs, discussion review concerns design intent). The failure mode is the *reviewer's own* unverified claim, an epistemic-honesty problem matching the `## Source-grounding rule` section's existing "Never guess" framing, not a criterion for judging the plan's text. Prompt-only enforcement matches the one existing precedent in the same section family (`Platform-behavior-claim verification`, also prompt-only). See `_mill/discussion.md`'s `mechanism-claim-rule-scope` / `mechanism-claim-rule-placement` / `mechanism-claim-rule-enforcement` Decisions for full rationale and rejected alternatives.
- **Applies to:** batch `mechanism-claim-rule` (the only batch).

## All Files Touched

- `plugins/mill/templates/review-plan-batch.md`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/unit_tests/test-review-templates.py`
