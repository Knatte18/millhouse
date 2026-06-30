I have verified the key claims. All source-grounding checks pass: mill-go/SKILL.md:738 contains `gate_cmd.lower()`; mill-start Phase: Select (lines 72-83) prints only `task.get('status', '')`; `get_task` returns the stored doc whose proposal lives in `body` and summary in `brief`; and `mill-ghissues-to-tasks` already uses `task['body']`. I found one concrete spec inconsistency and two cleanliness notes.

MILL_REVIEW_BEGIN
# Review: Fix drift-guard false positive and mill-start missing task body/brief

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-30
```

## Findings

### [GAP] Lock string form contradicts the snippet edit form
**Section:** Decisions → millstart-fetch-body-brief vs millstart-skill-regression-lock (+ Testing)
**Issue:** The Select snippet is specified as `task.get('body', '')` / `task.get('brief', '')`, but the Card 2 lock asserts the literal substring `task['body']` / `task['brief']`; existing locks use plain `in` checks (verified #495/#496), so `task.get('body', '')` does NOT contain `task['body']` and the prescribed TDD lock would fail even after a faithful edit.
**Fix:** Pin one literal form — require Phase: Explore's field documentation to contain the exact `task['body']` / `task['brief']` strings the lock checks, or change the lock to match the `.get('body'` form actually written.

### [NOTE] Lookbehind makes the entire ALLOWLIST dead
**Section:** Decisions → drift-regex-left-boundary; Technical context (ALLOWLIST)
**Issue:** Every current ALLOWLIST entry (`_path.*`, `_block.get`, `_str.strip`, etc.) is an identifier-tail match; the negative lookbehind stops those from being extracted at all, so all allowlist entries become unreachable dead code (harmless, but misleading).
**Fix:** State whether the now-redundant ALLOWLIST entries are pruned or intentionally retained, so the plan writer does not leave stale exemptions silently.

### [NOTE] Wiring of the new focused unit assertion is unspecified
**Section:** Testing (regex TDD candidate)
**Issue:** `main()` currently runs only `_run_drift_guard()` and `_run_regression_locks()`; the discussion adds `_extract_helper_references("gate_cmd.lower()") == []` and a positive-case assertion but does not say how they gate the exit code (new function / new card / inline in main).
**Fix:** Name where the focused assertions are invoked so they actually fail the suite on regression rather than sitting unused.

## Verdict

GAPS_FOUND
One concrete lock/edit string-form inconsistency must be reconciled before planning.
MILL_REVIEW_END
