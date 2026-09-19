MILL_REVIEW_BEGIN
# Review: mill-plan: Phase Plan Review's 4b/4c/4d re-validate gate says "7 kwargs", drops done_gate

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: /home/knatte/Code/millhouse/wts/mill-plan-done-gate-kwargs-count-drift/_mill/discussion.md
date: 2026-09-19
```

All claims verified against source (task-worktree paths):

- SKILL.md:250-283 — Phase: Plan's self-validate prose (line 251) and code block confirmed: 8 kwargs incl. `done_gate=cfg.get("pipeline", {}).get("done_gate")`, matches discussion verbatim.
- SKILL.md:565,581,597 — 4b/4c/4d confirmed as the only three "7 keyword arguments"/"same 7 kwargs" sites (grep for the exact phrase returns exactly these three lines, no fourth). 4d's elision claim (no repeated list, only "same 7 kwargs") confirmed.
- `_plan_validate.py:3687-3699` — `run()` signature confirmed: exactly 8 keyword-only params incl. `done_gate: str | None = None`, matching discussion's citation precisely.
- `millpy-review-plan.py:223,331` — both call sites confirmed already passing `done_gate=cfg.get("pipeline", {}).get("done_gate")`, supporting the "CLI was never wrong" claim.
- Testing section's `_check_verify_not_isolated`/`_is_python_project` claim confirmed (lines 2861-2926): PYTHONPATH= prefix required only when a Python-project marker exists, matching CLAUDE.md's convention; the `PYTHONPATH= true` fallback is consistent with actual enforcement.
- Both Decisions carry rationale + rejected alternative; scope in/out is unambiguous and matches the single-directional fix; no undecided items remain.

No BLOCKING or NIT findings this round.

## Verdict

APPROVE
Discussion accurately reflects source; scope, decisions, and testing claims all verified.
MILL_REVIEW_END
