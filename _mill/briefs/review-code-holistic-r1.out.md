MILL_REVIEW_BEGIN
# Review: _plan_validate and baseline verify gate gaps — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-24
```

## Verdict

APPROVE
All five cards are realised as planned, with no out-of-plan files and no cross-batch contract issues.

Verified against source:
- `_plan_validate.py`: `_check_card_numbering` starts-at-1 uses the specified tie-break and message. `_parse_cards_positioned`, `_requirements_fence_aware_span` and `_requirements_fence_open_lines` are added, and `_parse_cards` wraps the positioned version. All three emit sites in `_check_requirements_quote_indent_drift` carry `line`, with a `None` fallback that keeps the message well-formed.
- `_verify_baseline.py`: `_is_short_circuit_baseline`, the `None` return in `_signatures_for_pair`, and `None` pass-through in `compute_batch_baselines` (cache check kept, list copy kept) all match the plan.
- `millpy-implement.py`: the seed guard and the key-stays-absent `continue` before `set_batch_field` match the plan.
- Tests: the new tests for cards 1-5 are present in the five listed test files.
MILL_REVIEW_END
