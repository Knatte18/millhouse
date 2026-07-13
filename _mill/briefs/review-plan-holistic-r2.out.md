MILL_REVIEW_BEGIN
# Review: Port mill to POSIX, not just Windows — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-13
```

## Findings

### [BLOCKING] Card 5 preserves a non-existent `.ps1` wrapper mention
**Location:** Batch 1 / Card 5
**Issue:** `_shortcuts.py` (Card 5's own `Context:`) renders `.cmd` wrappers and explicitly `unlink`s any legacy `.ps1` (lines 8-9, 42, 75, 82), so `.millhouse/millpy-wikipush.ps1` exists on no platform; the Windows wrapper is `millpy-wikipush.cmd`. Card 5 mandates "Do not remove the Windows `.ps1` mention," which perpetuates a factual doc error the task is meant to correct.
**Fix:** Reword the requirement so `mill-wiki-push/SKILL.md:12` names the actual `.cmd` wrapper (or drops the wrapper filename), instead of preserving the stale `.ps1` reference.

### [NIT] Card 2 leaves the "Four checks" docstring prose stale
**Location:** Batch 1 / Card 2
**Issue:** `test-guards.py`'s module docstring header states "Four checks bundled into one test file" (line 3-4); Card 2 adds a fifth check and updates only the `Checks:` bullet list, leaving the count prose wrong.
**Fix:** Have Card 2 also update the "Four checks" sentence to "Five checks".

## Verdict

REQUEST_CHANGES
Card 5 enshrines a `.ps1` wrapper that no longer exists; fix the doc target.
MILL_REVIEW_END