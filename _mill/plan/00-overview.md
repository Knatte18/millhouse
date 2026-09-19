# Plan: mill-plan: Phase Plan Review's 4b/4c/4d re-validate gate says "7 kwargs", drops done_gate

```yaml
task: 'mill-plan: Phase Plan Review''s 4b/4c/4d re-validate gate says "7 kwargs", drops done_gate'
slug: mill-plan-done-gate-kwargs-count-drift
approved: true
started: 20260919-112514
parent: main
root: ""
verify: null
discussion_sha: 36eaa54f2ed65782daa3bf569c732d3d8e54404a
```

## Batch Index

```yaml
batches:
  - number: 1
    name: fix-plan-review-kwarg-drift
    file: 01-fix-plan-review-kwarg-drift.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: Doc-only fix, no code change

- **Decision:** This task edits only prose in `plugins/mill/skills/mill-plan/SKILL.md`. No `.py` file changes, no `_plan_validate.run` signature change, no behavior change to any CLI.
- **Rationale:** `_plan_validate.run`'s actual signature (confirmed by direct read of `plugins/mill/scripts/_plan_validate.py:3687-3699`) already has 8 keyword-only parameters including `done_gate`, and `millpy-review-plan.py`'s own step-1.5 gate (lines 223, 331) already calls it with `done_gate` included. The bug is exclusively that SKILL.md's own narrative description of Phase: Plan Review steps 4b/4c/4d says "7 keyword arguments" / "7 kwargs" and omits `done_gate` from the enumerated list, while Phase: Plan's own self-validate call (line 251) already correctly says "eight" and lists all eight. This decision is carried over verbatim from `_mill/discussion.md`'s Scope section.
- **Applies to:** all batches (there is only one).

### Decision: `verify: null` for this batch and module-wide

- **Decision:** Both this batch's own `verify:` and the overview's module-wide `verify:` are `null`.
- **Rationale:** The only change is prose inside a `SKILL.md` file. No unit test parses or exercises SKILL.md's narrative text, and `_plan_validate.py`'s own test suite (`plugins/mill/unit_tests/test-plan-validate.py`) tests the validator's Python behavior, not this file's prose — so there is no automatable regression surface for this change. Verification is by direct post-edit text inspection (see the batch's `## Batch Tests` section), not a runnable command.
- **Applies to:** all batches (there is only one).

## All Files Touched

- `plugins/mill/skills/mill-plan/SKILL.md`
