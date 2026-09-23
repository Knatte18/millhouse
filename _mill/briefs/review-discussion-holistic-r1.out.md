MILL_REVIEW_BEGIN
# Review: _plan_validate context-completeness: further false-positive/false-negative gaps, round 3

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-23
```

## Findings

### [BLOCKING:design] Joined-text scope breaks three line-wide exemptions' calibration
**Section:** Decision `line-join-refactor`
**Issue:** The decision runs `_is_literal_enumeration_exempt`, `_is_cross_card_ownership_exempt`, and `_is_illustrative_output_exempt` against the full joined Requirements body. Each is documented in source as an unconditional line-wide match deliberately calibrated to a single physical line (`_is_literal_enumeration_exempt`'s own docstring reasons about "3+ backtick tokens... on the same line"; `_is_cross_card_ownership_exempt`'s docstring accepts its line-wide tradeoff explicitly for "an unusually long Requirements: line"; `_is_illustrative_output_exempt` scans for any output verb "anywhere on the line"). Widening "line" to the entire joined Requirements body means one sentence's literal-value enumeration, ownership phrase, or output-verb mention now exempts every backtick token elsewhere in that card's Requirements text, including an unrelated genuine dependency several sentences away — a new false-negative class the round's own goal (fixing #1131's false positives without regressing coverage) doesn't want, and the Testing section has no case covering it.
**Fix:** Keep these three helpers scoped to their originating physical line (join only the tokenization plus the helpers that genuinely need cross-line reach, e.g. `_is_prohibition_exempt`), or explicitly re-justify each helper's threshold/tradeoff at whole-body scope and add a regression test proving a same-card dependency on one line survives an unrelated exemption-triggering phrase elsewhere in the same Requirements field.

## Verdict

REQUEST_CHANGES
One BLOCKING: line-join-refactor silently widens three line-wide exemptions to whole-body scope, an unaddressed false-negative regression.
MILL_REVIEW_END
