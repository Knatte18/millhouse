MILL_REVIEW_BEGIN
# Review: Port mill to POSIX, not just Windows

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-13
```

## Findings

### [NOTE] Per-file venv guard heuristic is coarse
**Section:** Scope > Regression guard; Testing
**Issue:** "line naming `.venv/Scripts/python.exe` must also name `.venv/bin/python` in the same file" passes any file that mentions `bin/python` anywhere, so a future Windows-only check added to a file that already has a `bin/python` line elsewhere slips through undetected.
**Fix:** Note the guard is a coarse tripwire (per-file, not per-block); accept as sufficient for the two known files, or scope it to the venv-existence check idiom specifically.

### [NOTE] test-bootstrap.sh prerequisites unstated
**Section:** Scope > test-bootstrap port; Technical context
**Issue:** The `.sh` port drives real scripts via a real venv/git but the discussion does not state behavior when `uv`/venv/git are absent on the runner (it is manual, not in run-all.py).
**Fix:** State the port assumes a synced venv + git present (same preconditions as the `.ps1`), and fails loudly rather than silently skipping.

## Verdict

APPROVE
Scope, decisions, and constraints are grounded and verified against source; only minor notes remain.
MILL_REVIEW_END