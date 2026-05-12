# Review: 33 (A) — Working-dir rename + portals redesign + junction cleanup

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-12
```

## Findings

### [NOTE] resolve_task_path module placement ambiguous
**Section:** § Decisions — task/ → _mill/ rename strategy; § Technical context
**Issue:** Both the Decisions section and the Technical Context write `_paths.py` **(or `_status.py`)`, leaving module placement unresolved. CLAUDE.md's path-invariants block explicitly states "New path-resolver helpers go here too — do not scatter" and points at `_paths.py`.
**Fix:** Drop the parenthetical `(or _status.py)` — the CLAUDE.md convention resolves this.

### [NOTE] recreate_active_junction mislabelled as needing target update
**Section:** § Technical context — key files; § Decisions — .active junction target
**Issue:** The Technical Context lists `_spawn_core.py: recreate_active_junction (update target)`. Verified against source: the function already targets `container_path / "portals" / slug` — correct for the redesign. What changes is (a) the portal creation call in millpy-spawn.py line 211 (currently `wiki/active/<slug>` becomes `wts/<slug>/_mill/`) and (b) the comment on lines 209-211 of millpy-spawn.py. A plan writer reading "update target" could change `recreate_active_junction` to point directly at `_mill/`, bypassing portals for hub `.active`.
**Fix:** Reword to: "`recreate_active_junction` — no code change needed; update caller comment in millpy-spawn.py (lines 209–211) that still says 'which in turn points to wiki/active/<slug>/'."

## Verdict

APPROVE
Two NOTEs; no GAPs blocking planning.