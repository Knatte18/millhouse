MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: false positives across gitignored/quoted/negated/citation/cross-reference prose — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-04
```

## Findings

### [NIT:consistency] Negation/contrast exemptions ordered after citation check, not before
**Location:** `plugins/mill/scripts/_plan_validate.py:2341-2356`
**Issue:** Card 5 (`01-validator-exemptions.md`) requires the non-dependency negation matcher to run "immediately after the existing `_is_prohibition_exempt` check and before the `_CITATION_MARKERS` check." The shipped order is prohibition (2341) → `_CITATION_MARKERS` (2345) → negation (2350) → contrast-citation (2355) — negation and contrast both land after the citation-marker check instead of before it.
**Fix:** Reorder the two `if` blocks to match the card's stated sequence, or note in the docstring/card that the sequence was intentionally changed to match the exemption's own numbered enumeration (1–10) for readability.
**Note:** Purely textual — every exemption here is an independent `continue`-on-True short-circuit with no shared state or side effect, so evaluation order never changes which tokens are flagged; all 34 new unit tests pass under the shipped order.

## Verdict

APPROVE
All eight exemptions, wiring, docstring, templates, and SKILL.md guidance match the plan; tests are complete and correctly registered.
MILL_REVIEW_END
