# Review: script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo — 01-foundation

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 01-foundation
date: 2026-05-04
```

## Findings

### [NIT] Card 4 references a non-existent standard-layout test
**Step:** Card 4 — `discover_active_worktrees`
**Issue:** The card says "The existing standard-layout test (no stub) must still pass", but `test-spawn-core.py` has no test for `discover_active_worktrees` at all — none in the test list, none in `main()`.
**Fix:** Add a standard-layout test (no stub, active marker at `entry/.millhouse/`) alongside the subfolder-install test; the "must still pass" assertion is vacuous as written.

### [NIT] Card 4 omits import update for `discover_active_worktrees`
**Step:** Card 4 — `test-spawn-core.py`
**Issue:** `test-spawn-core.py` imports from `_spawn_core` via an explicit name list; `discover_active_worktrees` is not in it, so any added test would fail with `NameError` unless the import block is updated.
**Fix:** Add `discover_active_worktrees` to the `from _spawn_core import (...)` block as part of the card's requirements.

## Verdict

APPROVE — two minor gaps in Card 4's test requirements; no blocking issues.