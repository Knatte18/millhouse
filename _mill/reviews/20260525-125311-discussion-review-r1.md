# Review: Finish V3 wiki adoption — complete batch 3 port and test sweep

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-25
```

## Findings

### [GAP] `_spawn_core.py` scope missing `_sidebar` import and calls
**Section:** § Scope — card 26 (`_spawn_core.py` finish); § Technical context ("Modules involved")
**Issue:** Card 26's scope lists `import _tasks_md` / `import _wiki` at lines 73–74 as the V2 imports to remove, but `import _sidebar` at line 70 is absent. Verified: `_sidebar.py` is deleted from the repo and `_spawn_core.py` also calls `_sidebar.regenerate(wiki_path)` at lines 515 and 658 (inside `multi_select_groom_then_claim` and `claim_in_wiki`). These are unaddressed chain-fail sources: any `import millpy_spawn` smoke after card 25/26 will still raise `ModuleNotFoundError: _sidebar`.
**Fix:** Add `import _sidebar` (line 70) to card 26's enumerated removals; add deletion (not replacement) of `_sidebar.regenerate(wiki_path)` at lines 515 and 658 — V3 daemon regenerates the sidebar internally, so callers simply drop these calls.

### [NOTE] Test sweep file lists appear stale for passes 2 and 3
**Section:** § Scope — "Test sweep V2 elimination" (cards 37, 38)
**Issue:** Pass 2 names `test-bg-launcher.py`, `test-millpy-validate-plan.py`, `test-review-cli.py` as having V2 `mock.patch` strings; Pass 3 names `test-millpy-bg.py`, `test-millpy-validate-plan.py`, `test-review-cli.py` as having V2 `Task(...)` fixture builders. Grep against all listed files finds zero V2 `mock.patch` strings and zero `_tasks_md.Task(` calls — these files appear already partially ported or the port was never needed.
**Fix:** Before writing cards 37/38, planner should re-verify actual V2 presence in these files from `_mill/plan/03-v2-deletion-and-port.md` on the parent branch (which the discussion already identifies as authoritative for this enumeration) rather than trusting the lists here.

## Verdict

GAPS_FOUND
One GAP: card 26's scope is missing `_sidebar` — the third deleted V2 module still present in `_spawn_core.py`.