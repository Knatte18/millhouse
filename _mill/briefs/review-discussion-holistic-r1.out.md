MILL_REVIEW_BEGIN
# Review: Fix mill-ghissues-to-tasks to refuse fold-ins into done and deferred tasks

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-15
```

## Findings

### [GAP] millpy-fold.py module docstring not in scope
**Section:** Scope (In) / Technical context (millpy-fold.py guard)
**Issue:** The module docstring at `millpy-fold.py` lines 10-17 hardcodes `LOCKED_FOLD_PHASES = ("active", "ready-to-merge", "pr-pending")` and the "phase-guard"/"plan frozen" rationale; scope only covers the guard code + import + value-assertion, leaving a stale doc block that contradicts the new allowlist (and re-introduces the removed constant name in prose).
**Fix:** Add the docstring (lines 10-17, and the "phase-guard" wording in lines 11/30) to the millpy-fold.py scope so the operation-order/guard description states the unclaimed-only allowlist.

### [NOTE] Allowlist relies on get_task always carrying deferred
**Section:** Technical context (millpy-fold.py guard) / Decision deferred-backlog-refused
**Issue:** `get_task` (`_store.py` line 252-256) returns the raw stored doc, not a projected dict; a doc inserted without the `deferred` key would lack it. Upsert defaults `deferred=False` so this holds today, but it is an implicit invariant the SKILL Step-5 inline check depends on.
**Fix:** Confirm the SKILL Step-5 re-check uses `task.get('deferred', False)` (not `task['deferred']`) as the discussion already prescribes `.get(...)` for the script — make the `.get` form explicit for the skill too.

### [NOTE] CLAUDE.md replacement wording left to implementer
**Section:** Constraints (CLAUDE.md line ~45)
**Issue:** The constraint says rewrite line 45 to "the allowlist rule" and drop the `_tasks_md.LOCKED_FOLD_PHASES` pointer (pointer is doubly stale — constant actually lives in `wiki/__init__.py`), but no target sentence is specified, risking inconsistency with the error-message/decision wording.
**Fix:** Specify the exact replacement text (e.g. "Fold only into unclaimed backlog tasks (`status is None AND not deferred`)") so all four doc surfaces stay consistent.

## Verdict
GAPS_FOUND
One stale-docstring scope gap; claims otherwise verified against source.
MILL_REVIEW_END
