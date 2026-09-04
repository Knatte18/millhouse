MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: misses bare symbol/identifier references entirely, only matches path tokens

```yaml
duration_s: 154.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version unconfirmed)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] Dotted `pkg.Symbol`/`Type.Method` search will not reliably find the declaring file
**Section:** Resolvability gate; Symbol-candidate shape
**Issue:** For the dotted form (`pkg.Symbol`, `reedengine.New`, `cell.CenterVerticalDepth`), a whole-word literal search for the *full qualified token* text will typically match caller sites, not the declaration — in idiomatic Go the declaring package's own file omits the self-qualifier (`func New(...)`, never `reedengine.New` on its own decl line), and in C# an instance-qualified access (`cell.CenterVerticalDepth`) uses an arbitrary local variable name unrelated to the type, so it essentially never appears verbatim at the property's declaration site. The design's own motivating examples (issue #966's `reedengine.New`, the Models repo's `cell.CenterVerticalDepth`) are exactly the cases this breaks: multiple call sites → "ambiguous, skip" (silently defeats the fix), a single caller elsewhere → resolves to that *caller's* file, not the real declaring file, producing a semantically wrong "declaring file."
**Fix:** Either resolve dotted tokens by searching for the trailing segment only (`Symbol`/`Method`, discarding the qualifier) with a documented rationale for why that's still "unambiguous," or explicitly acknowledge/scope out that dotted-form resolution is caller-site-based rather than declaration-based, and re-justify the "exactly one file = the file to flag against" premise for that case.

### [NIT:decision] Per-run caching left fully open despite the "must remain fast" constraint
**Section:** Technical context ("Consider" note); Constraints
**Issue:** Every symbol candidate triggers an uncached full source-tree filesystem walk; the discussion itself notes the same symbol can recur across many cards in one plan, yet caching is explicitly left to implementer judgment with "not required for correctness," while the Constraints section separately requires the check to "remain fast" as a synchronous pre-gate.
**Fix:** State a minimum expectation (e.g. per-token memoization within a single `run()` call is required, not optional) so the fast/offline constraint isn't satisfied only by accident of implementer diligence.

## Verdict

REQUEST_CHANGES
Dotted-symbol resolvability rests on a false premise about where qualified references appear in source.
MILL_REVIEW_END
