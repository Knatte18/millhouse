# Review: Replace psmux marker protocol with idle-prompt detection

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-22
```

## Findings

### [NOTE] Testing section contradicts Technical Context on which tests change
**Section:** Testing / `test-claude-sub.py` — updated/new scenarios
**Issue:** "S1–S5, S7–S9: update `extract_response` mock signature only" includes S2, S3, S5, and S8 — but those four tests have no `extract_response` mock (verified in source: they exit before Step 11) and the Technical Context section correctly classifies them as needing no changes.
**Fix:** Narrow the Testing section line to "S1, S4, S7, S9: update `extract_response` mock to 1-arg lambda; add `_wait_for_idle_stable` mock" to match the authoritative list in Technical Context.

### [NOTE] `_wait_for_idle_stable` unit scenarios not enumerated
**Section:** Testing / TDD candidates
**Issue:** `_wait_for_idle_stable` is named as a TDD candidate but no test scenarios are listed; the critical two-consecutive-poll behavior (the entire reason the function exists over `_wait_for_idle_prompt`) has no test to verify it was implemented correctly.
**Fix:** Add at minimum three scenarios: (a) first poll `❯` then second poll `❯` → True; (b) first poll `❯` then second poll no `❯` then two consecutive `❯` → True (transient recovery); (c) `❯` never appears → False on timeout.

## Verdict

APPROVE
Discussion is complete and self-consistent; both findings are documentation polish, not implementation blockers.