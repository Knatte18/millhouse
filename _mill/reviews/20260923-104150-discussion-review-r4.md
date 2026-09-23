MILL_REVIEW_BEGIN
# Review: _plan_validate context-completeness: further false-positive/false-negative gaps, round 3

```yaml
duration_s: 252.4
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-09-23
```

## Findings

### [BLOCKING:design] `_is_prohibition_exempt` widened to unbounded whole-body scope
**Section:** Decision `line-join-refactor`
**Issue:** `_is_prohibition_exempt` is listed separately from the clause-capped helpers and runs against the full joined Requirements body with no clause or bullet-proximity bound at all — a prohibition phrase anywhere in a long, multi-bullet Requirements field now exempts every backtick token in the entire field, not just a nested-bullet-adjacent one. The justification cited (the docstring's "nested-bullet/multi-line" gap) describes a parent/child-bullet proximity case, not whole-field reach — the fix goes further than the documented gap. This is the same false-negative class the same decision explicitly rejects widening for `_is_literal_enumeration_exempt`/`_is_cross_card_ownership_exempt`/`_is_illustrative_output_exempt`, just applied to a fourth helper instead.
**Fix:** Cap `_is_prohibition_exempt` the same way the clause-scoped helpers are capped (line-break/bullet boundary, or `_clause_bounds`), or explicitly scope it to the nested-bullet-adjacent case the docstring actually describes; add a negative test proving a prohibition phrase in one bullet doesn't exempt an unrelated genuine dependency several bullets away.

### [BLOCKING:design] Widened `_compute_declared_symbols_union` capture over-generalizes #1119's repro shape
**Section:** Scope `In`, item 4 (`_compute_declared_symbols_union`)
**Issue:** The new `modifier* identifier = value` capture form uses zero-or-more modifiers, so it also matches a bare `` `identifier = value` `` backtick span with no modifier/type annotation at all — ordinary prose citing an EXISTING repo constant's current value ("uses `` `timeout = 30` `` ``"), not a new inline declaration. #1119's own repro is `` `private const double StepDurationS = 10.0` `` — modifiers present. Matching the bare form too silently adds an existing symbol name to the plan-wide declared-symbols set, exempting a genuine later citation of that symbol from context-completeness anywhere else in the plan — a new, broad false-negative surface, since bare "x = value" prose is far more common than the paren/brace-shaped form this exemption already covers.
**Fix:** Require at least one modifier or type annotation before the `=` (matching the #1119 repro's own shape) rather than accepting a bare `identifier = value`, or otherwise narrow the new capture so it can't match a citation of an existing symbol's value.

### [NIT:design] No dedicated test for the empty plan-wide cited-files-set edge case
**Section:** Testing, `resolution-scope-rework` bullet
**Issue:** The narrowed resolver's "Accepted cost" (a symbol cited for the first time anywhere in the plan is never caught) implies an empty-cited-files-set boundary case — first card of first batch, before any Context:/Edits:/etc. accumulates — that the enumerated tests (a)/(b)/(c) don't explicitly name.
**Fix:** Add a fixture test with a fully empty plan-wide cited-files set, asserting no crash and the symbol branch simply finds nothing (never flags).

## Verdict

REQUEST_CHANGES
Two design gaps risk new false-negative classes the task's own stated goal explicitly rejects.
MILL_REVIEW_END
