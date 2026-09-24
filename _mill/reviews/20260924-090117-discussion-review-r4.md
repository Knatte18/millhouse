MILL_REVIEW_BEGIN
# Review: Prefix session names with repo short name; add MH:orch session

```yaml
duration_s: 237.7
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

## Findings

### [BLOCKING:design] Adding "orch" to DEFAULT_SESSIONS breaks worktree renders
**Section:** Decisions § Orch model/effort default
**Issue:** `resolve_sessions` (`_vscode_tasks.py`) validates every key in `DEFAULT_SESSIONS` unconditionally, before `TASK_SPECS` is iterated; adding `"orch"` to `DEFAULT_SESSIONS` means an invalid `spawn.sessions.orch.model`/`effort` in the shared `mill-config.yaml` raises `ValueError` on every worktree's `render_tasks`/`write_tasks` call too, not only the hub's — `TASK_SPECS` (worktree) never reads the `orch` entry, so this failure is pure collateral damage with no orch task involved.
**Fix:** Either scope `resolve_sessions` to the phases actually needed by the caller (`TASK_SPECS` vs `HUB_TASK_SPECS`) or state explicitly that hub-only config errors are accepted to break worktree spawns; the current rationale ("resolve_sessions iterates DEFAULT_SESSIONS, so the new key is picked up with no other change") is incorrect as a "no other change" claim.

## Verdict

REQUEST_CHANGES
One BLOCKING: orch-key validation leaks into worktree-only render paths, breaking spawn on bad hub config.
MILL_REVIEW_END
