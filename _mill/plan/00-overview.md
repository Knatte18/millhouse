# Plan: Self-discovered mill-go/mill-plan skill-doc and behavior gaps

```yaml
task: Self-discovered mill-go/mill-plan skill-doc and behavior gaps
slug: mill-pipeline-skill-doc-gaps
approved: false
started: 20260802-112647
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: mill-plan-self-validate-fixes
    file: 01-mill-plan-self-validate-fixes.md
    depends-on: []
    verify: null
  - number: 2
    name: mill-go-behavior-gaps
    file: 02-mill-go-behavior-gaps.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-phase-wait.py
  - number: 3
    name: harness-tool-contracts-doc
    file: 03-harness-tool-contracts-doc.md
    depends-on: [1, 2]
    verify: null
```

## Shared Decisions

### Decision: no CLI or script signature changes

- **Decision:** All three batches are documentation-only edits to `SKILL.md` files (plus one new reference doc and one test-file extension). No function signature in any `_*.py` helper changes. `_plan_validate.run`'s `skip_checks` parameter, `_phase_wait.matches_wait_trigger`'s signature, and `_status.read_batches` are all consumed as-is, unmodified.
- **Rationale:** Each of the five source issues (#753, #755, #757, #758, #759) is a narrow, mechanical fix to prose or a missing test case — no architecture change. Reusing existing, already-tested helpers keeps every batch's blast radius to the files it edits.
- **Applies to:** all batches.

### Decision: `Moves:` not used anywhere in this plan

- **Decision:** No card in this plan renames or relocates a file. Every card is a `Creates:` (one new doc) or an `Edits:` (existing `SKILL.md`/test-file prose).
- **Rationale:** None of the five source issues involve a rename.
- **Applies to:** all batches.

### Decision: sequential ordering to avoid same-file parallel-modifies-overlap

- **Decision:** Batch 3 (`harness-tool-contracts-doc`) depends on both Batch 1 and Batch 2 because it edits `plugins/mill/skills/mill-plan/SKILL.md` (also edited by Batch 1) and `plugins/mill/skills/mill-go/SKILL.md` (also edited by Batch 2), adding a one-line pointer to each in a section untouched by the other batch. Batches 1 and 2 touch disjoint file sets and have no dependency between them.
- **Rationale:** `_plan_validate`'s `parallel-modifies-overlap` check only exempts same-file edits across batches with an ancestor/descendant relationship; without the `depends-on` edges above it would fire for both overlaps.
- **Applies to:** batch 3.

## All Files Touched

- `plugins/mill/docs/harness-tool-contracts.md`
- `plugins/mill/skills/cli/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-phase-wait.py`
