# Plan: mill-plan: review-round cap and skip-check threading bugs

```yaml
task: "mill-plan: review-round cap and skip-check threading bugs"
slug: "mill-plan-review-round-cap-and-skip-check-threading"
approved: false
started: "20260904-082053"
parent: "main"
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: mill-plan-skill-round-cap-and-skip-check-fixes
    file: 01-mill-plan-skill-round-cap-and-skip-check-fixes.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: SKILL.md-only, no script changes

- **Decision:** This task edits only `plugins/mill/skills/mill-plan/SKILL.md`. `_plan_validate.py`, `millpy-review-plan.py`, `_plan_dag.py`, and `millpy-validate-plan.py` are read-only Context for citation accuracy but are never edited — every fix is expressible with capabilities they already provide (`_plan_validate.run`'s existing 7-kwarg signature; `millpy-review-plan.py`'s already-accepted `--max-rounds`/`--skip-check` flags).
- **Rationale:** Confirmed during discussion by reading both scripts' actual signatures/argparse definitions — no gap exists on the Python side.
- **Applies to:** all batches

### Decision: #934/#913 (skip-check threading) already resolved, out of scope

- **Decision:** No plan work targets `--skip-check`/`skip_checks` threading — it is already fully implemented on `main` (commits `3f6b5305`, `78dd2eef`), confirmed by `git diff main` showing zero prior changes to `mill-plan/SKILL.md` on this branch.
- **Rationale:** Re-verified line-by-line during discussion; every dispatch site (Agent-mode round dispatch, subprocess round dispatch, both ERROR-retry paths) already threads `plan_skip_checks`.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/skills/mill-plan/SKILL.md`
