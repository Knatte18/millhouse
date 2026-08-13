# Plan: mill-plan SKILL.md: entry, phase-gate, finalize, and re-entry path gaps

```yaml
task: 'mill-plan SKILL.md: entry, phase-gate, finalize, and re-entry path gaps'
slug: mill-plan-skilldoc-and-logic-bugs
approved: true
started: '20260813-082237'
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
    name: skill-doc-and-logic-fixes
    file: 01-skill-doc-and-logic-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py
```

## Shared Decisions

### Decision: Single batch, file-position card ordering

- **Decision:** All eight fixes land in one batch (`01-skill-doc-and-logic-fixes`), with cards ordered by their first-touched line position in `mill-plan/SKILL.md` (Entry section fixes first, then Phase: Plan, then Phase: Plan Review, then `## Principles`) — except the standalone `_paths.py` docstring card (card 2), which is sequenced immediately after its companion `worktree_root` binding card (card 1) since both resolve GitHub issues #839/#826 together.
- **Rationale:** Every fix is scoped to prose/logic inside a single ~580-line skill doc (plus one docstring line in `_paths.py`) — no shared subsystem boundary to split on, and per mill-plan's own "Batch sizing" guidance a batch is a smart unit a Sonnet builder can hold in its head; eight small, mostly non-overlapping textual edits to one file is exactly that unit. File-position ordering minimizes the chance of two cards' edits colliding on adjacent lines when applied in sequence, and keeps the implementer's mental model of "where am I in the file" monotonic.
- **Applies to:** all batches (there is only one).

### Decision: No script behavior changes — SKILL.md prose/logic and one docstring only

- **Decision:** Every card edits `plugins/mill/skills/mill-plan/SKILL.md` prose/logic, except card 2, which edits exactly one docstring line in `plugins/mill/scripts/_paths.py` with no signature or behavior change. No other script (`_status.py`, `_phase_wait.py`, `_plan_validate.py`, `_review_common.py`, `_config.py`, `_plan_dag.py`) is touched — every helper this plan's new SKILL.md prose calls already exists and already behaves correctly; the bugs being fixed are exclusively in how (or whether) `mill-plan/SKILL.md` calls them.
- **Rationale:** Matches `_mill/discussion.md`'s Scope section verbatim ("No script changes... every fix is text/logic inside `mill-plan/SKILL.md` itself, using helpers that already exist and already do the right thing").
- **Applies to:** all batches (there is only one).

## All Files Touched

- `plugins/mill/scripts/_paths.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
