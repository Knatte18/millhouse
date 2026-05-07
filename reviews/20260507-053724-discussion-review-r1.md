# Review: 24 (A) — mill-misc-fixes

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: discussion.md
date: 2026-05-07
```

## Findings

### [GAP] Q&A "All three" contradicts Scope on CLAUDE.md note

**Section:** Q&A log (Bug B entry) vs. Scope (In)

**Issue:** The Q asks whether to change the brace form, add a CLAUDE.md note, or document in `mill:cli`; the A says "All three" but then names only two actions (brace change + cli bullet). CLAUDE.md is absent from the Scope section. A plan writer reading the Q&A could conclude CLAUDE.md is in scope and add a note there, expanding scope unexpectedly.

**Fix:** Replace "All three" with "Both" in the Q&A answer, or add an explicit "No CLAUDE.md change — the global CLAUDE.md already has `${CLAUDE_PLUGIN_ROOT}` guidance via the project CLAUDE.md" line to Scope (Out).

---

### [NOTE] Pre-fix failing-test count inconsistency

**Section:** Testing (Cross-cutting)

**Issue:** "Pre-fix: 1 of 47 failing" reads as one test case failing, but Bug A states "Four unit tests fail." The "1" apparently means one test file, while "47" is a test-case count — mixing units in one sentence.

**Fix:** Write "Pre-fix: 4 of 47 test cases failing (all in `test-review-plan-flow.py`); Post-fix: 47/47 passing."

---

## Verdict

GAPS_FOUND  
One scope ambiguity on CLAUDE.md must be resolved before planning proceeds.