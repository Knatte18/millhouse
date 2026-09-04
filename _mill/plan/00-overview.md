# Plan: mill-go: done-gate halt path and cleanliness-gate recovery are under-documented

```yaml
task: "mill-go: done-gate halt path and cleanliness-gate recovery are under-documented"
slug: "mill-go-done-gate-halt-and-cleanliness-recovery"
approved: true
started: "20260904-083204"
parent: "main"
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: done-gate-run-gate
    file: 01-done-gate-run-gate.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-done-gate.py
  - number: 2
    name: handoff-pre-done-gate-and-lock-release
    file: 02-handoff-pre-done-gate-and-lock-release.md
    depends-on: [1]
    verify: null
  - number: 3
    name: cleanliness-gate-dead-parent-recovery
    file: 03-cleanliness-gate-dead-parent-recovery.md
    depends-on: [2]
    verify: null
  - number: 4
    name: step-5-5-liveness-probe
    file: 04-step-5-5-liveness-probe.md
    depends-on: [3]
    verify: null
  - number: 5
    name: mill-pause-agent-dispatch
    file: 05-mill-pause-agent-dispatch.md
    depends-on: []
    verify: null
  - number: 6
    name: cleanliness-pycache-allowlist
    file: 06-cleanliness-pycache-allowlist.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanliness.py
```

## Shared Decisions

### Decision: prose batches carry `verify: null`

- **Decision:** Batches 2, 3, 4, and 5 edit only `.md` skill files (orchestrator prose, no runtime Python surface introduced) — their frontmatter `verify:` is `null`, matching each batch's own `## Batch Tests` explanation.
- **Rationale:** `_mill/discussion.md`'s own Testing section is explicit: "everything else in this task is skill-file (prose) documentation with no new testable Python surface." mill's Python unit-test suite exercises in-memory/tempfile fixtures with no real git/LLM (per `mill:testing`) and cannot exercise orchestrator-prose control flow.
- **Applies to:** handoff-pre-done-gate-and-lock-release, cleanliness-gate-dead-parent-recovery, step-5-5-liveness-probe, mill-pause-agent-dispatch.

### Decision: batch 4 depends on batch 3 to avoid a same-file edit-order conflict, not a content dependency

- **Decision:** Batch 4 (`step-5-5-liveness-probe`) edits `plugins/mill/skills/mill-go-base/SKILL.md` step 5.5 (~lines 379-403); batch 3 (`cleanliness-gate-dead-parent-recovery`) edits the same file's step 2b (~lines 658-673) — a different, non-overlapping section. The two edits have no content dependency on each other, but both name `SKILL.md` in `Edits:`, so `_plan_validate.py`'s `parallel-modifies-overlap` check requires a `depends-on` edge between any two batches that are not already ancestor-related and share an `Edits:` path. Batch 4 depends on batch 3 (rather than the reverse) purely to satisfy this — either direction is equally valid.
- **Rationale:** mill-go executes batches sequentially in DAG order; without the edge, the two batches would be "parallel-eligible" per the validator's ancestor test and the same-file overlap would fail Step 1.5's pre-review gate.
- **Applies to:** cleanliness-gate-dead-parent-recovery, step-5-5-liveness-probe.

### Decision: `pipeline.done_gate` stays `null` — pre-existing repo-wide lint debt

- **Decision:** Per mill-plan's "Done-gate reminder," `ruff check .` was run against the current worktree tip (`git_root`) before considering it as a `done_gate` default. It exited non-zero with 1942 pre-existing findings unrelated to this task's scope. `pipeline.done_gate` is left `null` — no `mill-config.yaml` edit in this plan.
- **Rationale:** Setting `done_gate: ruff check .` would make every future task in this hub depend on fixing unrelated, pre-existing lint debt before it could reach `phase: done` — exactly the failure mode the reminder's own guidance warns against.
- **Applies to:** all batches (informational only — no batch edits `mill-config.yaml`).

## All Files Touched

- `plugins/mill/scripts/_cleanliness.py`
- `plugins/mill/scripts/_done_gate.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go-base/handoff.md`
- `plugins/mill/skills/mill-pause/SKILL.md`
- `plugins/mill/unit_tests/test-cleanliness.py`
- `plugins/mill/unit_tests/test-done-gate.py`
