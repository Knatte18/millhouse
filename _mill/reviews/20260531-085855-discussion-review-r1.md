# Review: haiku-implementer-reliability

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-31
```

## Findings

### [GAP] Brief-size guard disabled-by-default condition is ambiguous
**Section:** Decisions › brief-size guard in millpy-implement.py
**Issue:** The stated check `len(prompt_text) > cfg.get("llm", {}).get("max_implementer_prompt_chars", 0)` reduces to `len(prompt_text) > 0` when the key is absent, which fires for every non-empty prompt — contradicting "Default `0` means the guard is disabled." The `(and max_implementer_prompt_chars > 0)` parenthetical tries to express a two-part condition but a plan writer following the literal check produces always-firing behavior.
**Fix:** State the compound condition explicitly: `max_chars = cfg.get("llm", {}).get("max_implementer_prompt_chars", 0); if max_chars > 0 and len(prompt_text) > max_chars:`.

### [NOTE] Existing test case counts are incorrect
**Section:** Technical context › Existing unit test coverage
**Issue:** Discussion says test-cleanliness.py has "6 cases for `compute_new_dirt`" — the file has 8 (cases 1–8, verified) plus 1 for `capture_snapshot` (9 total). It says test-implementer-common.py has "5 cases" — the file has 6 (cases 1, 2, 3, 3b, 4, 5, verified).
**Fix:** Update counts to 8 compute_new_dirt + 1 capture_snapshot (9 total), and 6 for implementer-common; incorrect baselines may cause confusion when the plan writer adds new cases.

## Verdict

GAPS_FOUND
Brief-size guard disabled-by-default requires a compound condition to be stated explicitly before planning.