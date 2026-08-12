MILL_REVIEW_BEGIN
# Review: _plan_validate: context-completeness fires on forbidding/explanatory file mentions

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [BLOCKING:design] `write`'s inflected-form categorization contradicts the section's own rules
**Section:** Decisions > Prohibition-detection redesign, inflected-verb-forms bullet.
**Issue:** `write` ends in silent `e` (like the 11-verb silent-e-drop group) yet is excluded from that list and instead bundled into "fully irregular ... alongside the regular-pattern `writes`/`wrote`/`writing`." `writing` actually requires the silent-e-drop rule (naive concatenation gives `writeing`), and `wrote` is a fully suppletive irregular past tense derivable from none of the three stated rules — so labeling these two as "regular-pattern" self-contradicts the rules stated one sentence earlier, and an implementer deriving forms programmatically per the stated categorization (rather than copying the literal spelled example) reproduces the exact naive-suffix-concatenation bug round 4 exists to prevent.
**Fix:** State `write` is doubly irregular — needs the silent-e-drop rule for `-ing` (like the 11-verb group) plus fully suppletive `wrote`/`written` for the past forms — and enumerate all five forms (`write`/`writes`/`wrote`/`writing`/`written`) literally rather than attributing three of them to "regular-pattern" derivation.

### [NIT:consistency] No regression-test scenario named for `write`'s irregular forms
**Section:** Testing > New scenarios to cover.
**Issue:** The new-scenario list names verb/negation combos for `edit`, `add`, `link`, `read`, and a contraction, but not `write` — the one verb whose inflected-form derivation is most error-prone per the finding above.
**Fix:** Add a scenario exercising `write`'s irregular forms (e.g. "do not write to `foo.py`" and "must not have written `bar.py`") to catch the categorization bug at test time.

## Verdict

REQUEST_CHANGES
Fix the self-contradictory `write` inflected-form categorization before plan writing proceeds.
MILL_REVIEW_END
