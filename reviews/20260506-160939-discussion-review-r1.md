# Review: 21 (A) — mill-go cleanliness gate fixes

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: discussion.md
date: 2026-05-06
```

## Findings

### [NOTE] Bug A fix makes Bugs B and C gate-redundant
**Section:** Problem / Decisions
**Issue:** `--untracked-files=no` (Bug A fix) already filters `??` lines, so untracked review files from Bugs B and C would never reach the gate; the B/C fixes are hygiene improvements, not additional gate fixes.
**Fix:** Add a sentence clarifying that B/C are committed for repository cleanliness, not as independent gate fixes, so the plan writer understands the full rationale.

### [NOTE] mill-plan 4b excluded without explanation
**Section:** Scope / Technical context
**Issue:** Step 4b also has a vague "commit+push (single commit covering plan + reviews + status)" with no explicit git command — the same pre-fix state as 4a — but the scope excludes 4b without justification.
**Fix:** Note that 4b is intentionally excluded because Bug A's fix makes its untracked file moot and 4b's description already mentions "reviews" in the commit scope.

## Verdict

APPROVE  
All three bugs verified in source; decisions are sound with clear rationale and rejected alternatives.