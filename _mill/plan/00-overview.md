# Plan: mill-go / mill-plan loop hardening

```yaml
task: "mill-go / mill-plan loop hardening"
slug: mill-orchestration-loop-hardening
approved: false
started: "20260528-214851"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: review-guard-overstep
    file: 01-review-guard-overstep.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-pygit2-util.py test-review-guard.py
  - number: 2
    name: code-review-nit-envelope
    file: 02-code-review-nit-envelope.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-code-flow.py
  - number: 3
    name: plan-review-cli-and-validator
    file: 03-plan-review-cli-and-validator.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-cli-error-envelope.py test-plan-validate.py
  - number: 4
    name: status-phase-timestamp
    file: 04-status-phase-timestamp.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-status.py
  - number: 5
    name: mill-go-skill
    file: 05-mill-go-skill.md
    depends-on: [2, 4]
    verify: null
  - number: 6
    name: mill-plan-skill
    file: 06-mill-plan-skill.md
    depends-on: [3]
    verify: null
  - number: 7
    name: mill-start-skill
    file: 07-mill-start-skill.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: helper-then-consumer ordering

- **Decision:** Each new Python helper is added in its own card/batch before the card that consumes it. `is_ancestor` (batch 1, card 1) lands before the overstep guard rework (card 2) that calls it. `nit_count` on `ReviewResult` (card 3) lands before `_review_code` populates it (card 4). `phase_entry_timestamp` (batch 4) and the validator/CLI changes (batch 3) land before the SKILL batches (5, 6) that document them.
- **Rationale:** Cold-start implementers and reviewers see the finalized helper signature before any caller relies on it.
- **Applies to:** all batches

### Decision: shared-file serialization via depends-on

- **Decision:** `plugins/mill/scripts/_review_common.py` is edited by batch 1 (overstep guard) and batch 2 (`ReviewResult.nit_count`); batch 2 declares `depends-on: [1]` so the two never run in parallel. `plugins/mill/scripts/millpy-review-plan.py` is edited only within batch 3 (both the `main()` wrap and the validate-threshold wiring), so no cross-batch edge is needed for it.
- **Rationale:** Two parallel-eligible batches editing the same file is a plan defect (`parallel-modifies-overlap`). Serializing with an explicit edge keeps the DAG legal and the edits conflict-free.
- **Applies to:** review-guard-overstep, code-review-nit-envelope, plan-review-cli-and-validator

### Decision: SKILL.md batches carry verify: null

- **Decision:** Batches 5, 6, 7 edit only `SKILL.md` prose and have `verify: null`. Their `## Batch Tests` sections state the prose is verified by the holistic plan/code reviewer, not a test harness.
- **Rationale:** SKILL.md files have no runnable surface; there is nothing for `verify:` to exercise.
- **Applies to:** mill-go-skill, mill-plan-skill, mill-start-skill

### Decision: paths are worktree-relative

- **Decision:** All `Context:`/`Edits:` paths are worktree-relative (e.g. `plugins/mill/scripts/_review_common.py`). The new `out-of-worktree-target` validator check (card 8) is precisely the gate that rejects absolute / home-dir targets, so this plan must not contain any.
- **Rationale:** Consistency with existing plan convention and with the check this task introduces.
- **Applies to:** all batches

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_pygit2_util.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-pygit2-util.py`
- `plugins/mill/unit_tests/test-review-cli-error-envelope.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-guard.py`
- `plugins/mill/unit_tests/test-status.py`
