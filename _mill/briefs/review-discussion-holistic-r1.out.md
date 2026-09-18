MILL_REVIEW_BEGIN
# Review: _plan_validate.py _resolve_symbol_files: naive whole-file text search, no declaration-form check

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet 5)
reviewed_file: /home/knatte/Code/millhouse/wts/plan-validate-context-completeness-symbol-branch-bugs/_mill/discussion.md
date: 2026-09-18
```

## Findings

### [BLOCKING:consistency] Qualifier-disambiguation vs. search_key-only cache contradiction
**Section:** Decision `qualifier-disambiguation` vs. Technical context (cache paragraph)
**Issue:** The Decision has `_resolve_symbol_files` accept the qualifier and filter multi-matches internally, but the existing cache is looked up/stored by `search_key` alone (`if search_key in cache: return cache[search_key]`, confirmed at line 2002). Two dotted tokens sharing a trailing segment but different qualifiers (e.g. `reedengine.New` then `otherpkg.New`) would hit the cache from the first call and silently get the first call's qualifier-filtered result.
**Fix:** Decide explicitly: either the raw (unfiltered) match list stays cached under `search_key` and qualifier-filtering happens strictly downstream of every cache lookup (including hits), or the cache key becomes composite `(search_key, qualifier)`. The Technical context paragraph already flags this as open ("consider whether...") — it needs to be a Decision, not an implementer TBD.

### [BLOCKING:design] Python declaration-form regex omits variable/attribute declarations
**Section:** Decision `declaration-form-regex`, Python bullet
**Issue:** Go's regex set includes `const`/`var` top-level and grouped-block forms, C#'s includes modifier-prefixed field/property assignment, TS's includes `const|let|var` — but Python's is only `(def|class) SYMBOL`, with no form for a module-level constant or class-body attribute (`SYMBOL = ...`, `SYMBOL: type`). A Python symbol whose only real declaration is such a line — previously matched by the naive whole-file search — will now permanently resolve to zero matches, silently disabling the symbol check for that entire declaration category in the one language given no assignment-form coverage.
**Fix:** Either add a Python assignment/annotation declaration form (module- or class-level `SYMBOL = ` / `SYMBOL:`) to keep language coverage comparable, or explicitly decide-and-state this is an accepted Python-only regression and say why.

### [NIT:scope] Testing plan under-covers declaration-form regex for 2 of 4 languages
**Section:** Testing, "Declaration-form matching" bullet
**Issue:** The declaration-form-regex Decision commits to all four extensions, but the testing bullet only requires "at least Go and one non-Go extension (C# recommended)" for declaration-vs-usage cases — TypeScript's and (especially, given the finding above) Python's declaration regex have no stated test obligation.
**Fix:** Extend the minimum coverage requirement to all four extensions, or state why TS/Python are lower-risk and can skip dedicated declaration-vs-usage fixtures.

## Verdict

REQUEST_CHANGES
Cache/qualifier interaction is unresolved and Python declaration coverage has a real gap.
MILL_REVIEW_END
