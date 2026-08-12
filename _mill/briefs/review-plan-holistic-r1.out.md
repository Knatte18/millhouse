MILL_REVIEW_BEGIN
# Review: _plan_validate: context-completeness fires on forbidding/explanatory file mentions — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: plan/
date: 2026-08-12
```

## Findings

### [NIT:consistency] Redundant negation entries in `_PROHIBITION_NEGATIONS`
**Location:** batch `prohibition-regex-generalization` / Card 1
**Issue:** `"do not"`, `"does not"`, `"must not"`, `"shall not"` each contain the standalone word `"not"`, which is also a tuple entry (`\bnot\b`) — those four multi-word entries can never independently match anything the bare `"not"` entry doesn't already catch.
**Fix:** None required for correctness; optionally drop the four subsumed phrases or add a one-line comment noting they're kept for self-documentation despite being logically redundant with `"not"`.

### [NIT:scope] Missing symmetric negative test: verb present, no negation
**Location:** batch `regression-tests` / Card 3
**Issue:** `_is_prohibition_exempt` requires negation AND verb; Card 3's test 4 proves negation-without-verb is not exempted, but no new test proves verb-without-negation is not exempted either (e.g. a line containing `"remove"`/`"touch"` but no negation word, naming a genuine unlisted dependency).
**Fix:** Add a fifth regression test mirroring test 4 but swapping which conjunct is present, to cover both failure modes of the AND predicate.

## Verdict

APPROVE
Plan is thoroughly source-grounded, faithfully implements the Shared Decision, and both findings are cosmetic.
MILL_REVIEW_END
