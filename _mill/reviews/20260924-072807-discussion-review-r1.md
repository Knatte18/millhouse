# Review: Remove batch review (plan-review.batch / code-review.batch)

```yaml
verdict: APPROVE
reviewer_model: orchestrator
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

## Findings

### [NIT:consistency] Env-override table is named ENV_REGISTRY, not ENV_OVERRIDES
**Section:** Scope (Config), Technical context, Testing
**Issue:** The discussion says `ENV_OVERRIDES` "(lines ~46–52)" and tests that the two vars are "gone from `ENV_OVERRIDES`". In `_config.py` the table is `ENV_REGISTRY` (line 45); the entries `MILL_PLAN_BATCH_REVIEWER` and `MILL_CODE_BATCH_REVIEWER` are there.
**Suggested fix:** Use `ENV_REGISTRY` in all three places so the plan and the test assertion name the real symbol.

### [NIT:scope] `mill-go2/SKILL.md` is not listed but carries a batch scope
**Section:** Scope (Skills)
**Issue:** `mill-go2/SKILL.md` says "`{scope}` is the batch name, or `holistic`" for the fixer fork-fallback (log, notify and commit message forms). With batch review gone, `{scope}` is only `holistic`. The discussion only covers this through the generic "any other skill text found by grep".
**Suggested fix:** Name `mill-go2/SKILL.md` in the Skills list and say whether the `{scope}` wording is narrowed to `holistic` or left as-is.

### [NIT:decision] Summary-parser test is left as "if present"
**Section:** Testing
**Issue:** "`test-review-summary` (if present) or a new case" is non-committal. `unit_tests/test-review-summary.py` exists, so the alternative is not needed.
**Suggested fix:** State that the case is added to `test-review-summary.py`.

## Verdict

APPROVE
The scope, decisions and rejected alternatives are consistent with the code I checked: `_moves_check` and `rename_detect_pct` have no consumer outside per-batch finalize, `walk_unknown_keys` reports the whole `roles.<role>.batch` block as one dotted path (so a `RENAMED_KEY_HINTS` entry on the block path matches), and only the three NITs above need correcting in the plan.
