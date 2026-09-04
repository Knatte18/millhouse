MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: misses bare symbol/identifier references entirely, only matches path tokens

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: /home/knatte/Code/millhouse/wts/plan-validate-context-completeness-missing-symbol-refs/_mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:consistency] "looks like code" signal definition excludes its own motivating examples
**Section:** Decisions › Symbol-candidate shape; Decisions › Resolvability gate (rationale)
**Issue:** The shape decision defines the signal as "an uppercase letter **after** that segment's position 0 (CamelCase/mixedCase), or an underscore" — i.e. an internal capital, position-0 explicitly excluded. Under this literal rule, a single initial-capitalized word with no internal capital (`New`, `Zone`, `Get`, `Run`, `None`, `True`, `False`) has **no** qualifying signal: its only uppercase letter is at position 0. Yet `reedengine.New`'s trailing segment `New` is exactly this shape (qualifier `reedengine` is all-lowercase, `New` has no internal capital), so by the decision's own literal test `reedengine.New` would be rejected at the shape gate and never reach resolution — directly contradicting the Rationale bullet's claim that `reedengine.New` is covered ("every one of which has CamelCase/mixedCase... in at least one segment") and the Scope-in bullet listing it as covered example. The same contradiction recurs verbatim in the Resolvability-gate rationale, which asserts `None`/`True`/`False` "satisfy the 'uppercase after position 0' signal" — they do not, by the same literal reading (cap only at position 0).
**Fix:** Resolve the contradiction explicitly: either (a) change the signal to "contains an uppercase letter anywhere, including position 0, as long as the rest isn't all-caps" (which would then admit `New`/`None`/`True`/`False` as the rationale assumes), or (b) keep "after position 0" strictly and update the Rationale/Scope/Resolvability-gate/Testing sections to drop `reedengine.New` and `None`/`True`/`False` as covered examples and explain how single-word exported Go symbols (a common real-world case per the source issues) are otherwise handled. As written, the Testing section's "Dotted candidate resolves via trailing segment" case (`` `reedengine.New` `` must be flagged as unresolved-elsewhere) is unimplementable under the literal shape rule — the candidate would be silently excluded before resolution is attempted, not flagged.

## Verdict

REQUEST_CHANGES
Shape-signal definition contradicts its own rationale/testing examples for single-capital words like `New`/`None`.
MILL_REVIEW_END
