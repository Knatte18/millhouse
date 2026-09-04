MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: false positives across gitignored/quoted/negated/citation/cross-reference prose — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4-5
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [NIT:consistency] Batch 2 test-function counts don't add up
**Location:** batch 02-structural-exemption-tests, Card 12 / Batch Tests **Issue:** Card 12's header says "Add five test functions" but its own bullets enumerate six (the final bullet, "one clean case plus its mirror," is a clean+dirty pair per the file's established one-fixture-one-assertion convention, i.e. two functions); summing all five cards' stated counts (3+5+3+5+1) gives 17, but "Batch Tests" says "the fourteen or so new test functions." **Fix:** Correct Card 12's own header to "six" and update the Batch Tests count to match the true total (verified: batch 3's analogous "sixteen" is arithmetically correct, so only batch 2's counts need correcting).

### [NIT:design] New Creates-to-card-key parameter's default value idiom unspecified
**Location:** batch 01-validator-exemptions, Card 4 **Issue:** "pass it to `_check_context_completeness` as a new keyword-only parameter defaulting to an empty mapping" doesn't say whether that's a literal `= {}` default (harmless here since the function only reads the map, but still a mutable-default anti-pattern an implementer or ruff would flag) or the safer `= None` + in-body materialization idiom. **Fix:** State the `None`-default-then-materialize-to-`{}` idiom explicitly in Card 4's Requirements to avoid the ambiguity outright.

## Verdict

APPROVE
Verified every exemption's mechanism claims against source; only two low-impact documentation/style NITs found, no BLOCKING issues.
MILL_REVIEW_END
