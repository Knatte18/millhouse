# Plan: mill-plan SKILL.md: step 6 max-rounds escape bugs, self-run validator citation errors, and Step 1.5 fix-table wrong remedies

```yaml
task: 'mill-plan SKILL.md: step 6 max-rounds escape bugs, self-run validator citation errors, and Step 1.5 fix-table wrong remedies'
slug: mill-plan-step6-and-fixtable-bugs
approved: false
started: '20260814-092916'
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: skillmd-blocked-resume-and-fixtable-fixes
    file: 01-skillmd-blocked-resume-and-fixtable-fixes.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: revise_from_blocked flag naming

- **Decision:** Entry step 4's `--revise` pre-check binds a second local boolean, `revise_from_blocked`, alongside the existing `revise_requested`. `revise_from_blocked` is `True` only when the pre-check's `phase == "blocked"` branch fires; it is `False` (or left unbound, treated as falsy) on the `planned+approved` branch, and is never set at all when `revise_requested` is not set. All cards in this batch must use these exact two names — no synonyms, no renaming.
- **Rationale:** Phase: Plan Review needs to distinguish a blocked-resume `--revise` from a planned+approved `--revise` at its own Path Setup step, where the two must be handled differently (the `revise-{N+1}` reviews-subdir namespacing override applies to the latter but must NOT apply to the former — a blocked-resume continues the same never-approved round sequence rather than starting a fresh revision pass over an approved plan). A bare `revise_requested` flag cannot make that distinction on its own.
- **Applies to:** all batches (single batch in this plan).

### Decision: no Python code or test changes

- **Decision:** this plan makes zero changes to any `.py` file. Every edit is a prose/control-flow change to `plugins/mill/skills/mill-plan/SKILL.md`. No new unit tests are added, and no existing test file is modified.
- **Rationale:** per `_mill/discussion.md`'s Testing section — both in-scope issues (#852, #853) are pure `SKILL.md` prose changes with no new executable code path. The underlying machinery this plan reuses or reorders (`_status.set_blocked`, `_status.append_phase`, `_review_common.discover_round`, `millpy-review-plan.py`'s existing `--max-rounds` flag, `_plan_validate.py`'s `_verify_command_has_any_tag`) is not itself modified or behaviorally changed — only how `mill-plan/SKILL.md` instructs the orchestrator to invoke/thread it. Existing coverage (`test-plan-validate.py`, `test-millpy-validate-plan.py`, `test-review-plan-flow.py`, `test-review-plan-finalize-round.py`, `test-status.py`) already exercises that machinery and needs no modification.
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/skills/mill-plan/SKILL.md`
