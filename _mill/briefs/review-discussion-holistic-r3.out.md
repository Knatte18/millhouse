MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: misses bare symbol/identifier references entirely, only matches path tokens

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:consistency] Resolvability gate still says dotted text is "compared against own refs"
**Section:** Decisions > Resolvability gate (closing clause of the Decision paragraph). **Issue:** This clause states "the full dotted text is still what gets shape-matched and still what's compared against the card's own refs," but the later "Membership check" and "Reverse path-canonicalization (r2 fix)" decisions establish unambiguously that what's compared against `own_refs` is the **canonicalized resolved file-path string** (via `.relative_to()` + `.as_posix()`), never the symbol token text itself — `own_refs` holds author-typed path tokens, not symbol names. **Fix:** Strike or rewrite this leftover clause to say only that the full dotted text is what gets shape-matched; the comparison-against-own-refs mechanism is owned entirely by the two later, more specific decisions.

### [NIT:consistency] Keyword-suppression rationale contradicts the shape gate's own example
**Section:** Decisions > Resolvability gate (Rationale). **Issue:** Claims the exactly-one-file gate "organically suppresses common keywords (`nil`, `true`, `false`, `null`)," but `true` is already used as the Symbol-candidate-shape decision's own example of an all-lowercase word the *shape gate* excludes before resolvability search ever runs — these tokens never reach the resolvability gate. **Fix:** Drop or correct the keyword-suppression claim to describe the shape gate as the actual filter, or cite an example keyword that plausibly has CamelCase/underscore/dot shape.

### [NIT:scope] No test named for the "required, not optional" per-search-key cache
**Section:** Technical context (memoization requirement) / Testing. **Issue:** The per-run `dict[str, list[Path]]` memoization is called out as "correctness-adjacent, not free-form implementer discretion," yet the otherwise-thorough Testing list (10 bullets) names no case exercising cache reuse across repeated occurrences of the same symbol. **Fix:** Add a testing bullet asserting the underlying search is invoked once per unique search key even when the symbol recurs across multiple cards (e.g. via an injected call-counting search stub).

## Verdict

REQUEST_CHANGES
Stale clause in Resolvability gate contradicts the r2-fixed comparison mechanism; must be reconciled before plan writing.
MILL_REVIEW_END
