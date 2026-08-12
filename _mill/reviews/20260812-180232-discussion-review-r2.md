MILL_REVIEW_BEGIN
# Review: _plan_validate: context-completeness fires on forbidding/explanatory file mentions

```yaml
duration_s: 164.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; the environment's stated model ID is claude-sonnet-5, which I cannot independently confirm)
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [BLOCKING:design] Verb-list substring matching creates realistic false-negative collisions
**Section:** Decisions > Prohibition-detection redesign (tradeoff paragraph) **Issue:** The decision explicitly keeps "the same line-wide granularity as today's substring match" for both negation and verb word sets. Several verb words are short enough to be accidental substrings of common English words (`use`⊂"because"/"used"/"cause", `add`⊂"address"/"additional", `move`⊂"removed", `cite`⊂"excite"), and negation includes bare `not`. A wholly plausible mill-plan sentence — "Read `src/a.py` because it does not export the helper directly." — contains `not` + `use` (via "because") and would be silently exempted from context-completeness despite naming a genuine dependency. **Fix:** Decide and state whether verb/negation matching is whole-word (regex `\b...\b`) or substring, and if substring, either drop the shortest collision-prone verbs or add word-boundary matching to the design; the existing tradeoff analysis only considers clause-level ambiguity, not this substring-collision failure mode.

### [NIT:consistency] `_check_context_completeness` line range in Technical context is wrong
**Section:** Technical context, `_check_context_completeness: lines 1528-1596` **Issue:** Source read confirms the function's `def` starts at line 1469 (docstring runs to ~1523); lines 1528-1596 only cover the tail of the function body, not its full span, unlike every other cited range in this section which matches exactly (verified `_extract_requirements_text` 1393-1414, `_card_own_reference_set` 1417-1466, `_check_verify_full_suite` 2173-2235, wiring 2726/2739 all exact). The marker-check sub-range 1547-1553 is itself correct. **Fix:** Correct the function's line range to 1469-1598 (or clarify the citation is intentionally scoped to the body only).

### [NIT:consistency] "Double negatives" limitation promised in Q&A but dropped from Scope/Decisions
**Section:** Q&A log (5th entry) vs. Scope "In" / Decisions **Issue:** Q&A commits to documenting "known heuristic limitations (e.g. double negatives, nested bullets)" as a Known-limitations note, but Scope's "In" bullet and the Decisions section only mention the nested-bullet/multi-line case — double negatives never resurfaces as a concrete documentation target. **Fix:** Either add double-negative handling to the Scope "In" documentation bullet, or drop the "double negatives" example from the Q&A answer to avoid an unfulfilled commitment.

## Verdict

REQUEST_CHANGES
Substring-based verb/negation matching risks silently exempting genuine dependencies on common English phrasing.
MILL_REVIEW_END
