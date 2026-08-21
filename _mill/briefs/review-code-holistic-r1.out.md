MILL_REVIEW_BEGIN
# Review: millpy-review-plan: finalize envelope verdict silently diverges from the review file's own written verdict — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-21
```

## Findings

No findings. The single-batch implementation matches the plan verbatim.

Verified in `_review_common.py:2620-2625` — the verdict-recomputation block is exactly the
three-way branch the plan specifies (`blocking_count > 0` -> `REQUEST_CHANGES`; `elif
demoted_any` -> `APPROVE`; else `original_verdict` left untouched), with the downstream
`rewrite_verdict_token` gate (`:2630`, still `demoted_any and verdict != original_verdict`) and
`append_demotion_note` gate (`:2637`, still `demoted_any`) both unchanged as required. The
docstring paragraph (`:2564-2572`) matches the plan's replacement text.

Card 2's two new tests (`test-review-class-taxonomy.py:563-621`) reproduce the NIT-only
zero-blocking repro exactly as specified, assert both the envelope and written-file conditions
the plan lists, and are registered in `TESTS` immediately after the
`test_verdict_token_rewritten_for_plan_and_code_types` entry (`:742-753`), without touching any
pre-existing test body or entry.

Card 3's `_run_cli_test` extension (`test-review-cli-error-envelope.py:61,89-90`) and the three
new `..._finalize_missing_agent_output_is_usage_error` methods are each placed immediately after
their CLI's `..._pre_launch_error_includes_round` sibling, asserting the exact five conditions
the card specifies. Cross-checked against the actual CLI source
(`millpy-review-plan.py:265-268`, `millpy-review-discussion.py:205-211`,
`millpy-review-code.py:236-239`, and `print_error_envelope`'s `error_kind="usage"` default in
`_review_cli.py:24-58`) — the tests pin real, already-correct behavior, not a re-implementation.

No out-of-plan files, no duplicated helpers, no cross-batch contract issues (single batch, no
dependents). The dropped "fourth candidate bug" scope item is confirmed absent from the diff —
`millpy-review-plan.py`'s `except ReviewError` handlers (lines 192-193, 259-260, 307-308,
353-354) are unchanged, consistent with `discussion.md`'s decision to reject that item.

## Verdict

APPROVE
Fix, docstring, and both test cards match the plan exactly with no scope creep or regressions.
MILL_REVIEW_END
