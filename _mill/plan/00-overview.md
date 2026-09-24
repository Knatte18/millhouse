# Plan: mill-go-base / mill-plan documentation gaps

```yaml
task: "mill-go-base / mill-plan documentation gaps"
slug: "mill-go-plan-doc-gaps"
approved: false
started: "20260924-063248"
parent: "main"
root: ""
verify: null
discussion_sha: "70e5d803dce7b83965f35c03a068e875808f7df1"
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: inferred-success-log
    file: 01-inferred-success-log.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py
  - number: 2
    name: commit-none-and-done-gate
    file: 02-commit-none-and-done-gate.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: doc-only-change

- **Decision:** Every card edits prose (SKILL.md, templates) or one docstring.
  No runtime behaviour, `inferred` emission, or `_plan_validate` check changes.
- **Rationale:** The discussion scopes this task to instruction-level fixes; the runtime behaviour is already correct.
- **Applies to:** all batches

### Decision: semantic-line-breaks

- **Decision:** New markdown prose is written one sentence per line, with an extra break at an internal independent-clause boundary, per the `prose` skill.
  Existing long lines are edited in place only where a card names them; untouched lines are not reflowed.
- **Rationale:** CLAUDE.md conventions; keeps future single-word edits diff-local.
- **Applies to:** all batches

### Decision: no-hub-config-edit

- **Decision:** No card edits hub `mill-config.yaml`, and no `skip_checks` entry is needed.
- **Rationale:** Out of scope per the discussion; an edit would trip the `wiki-config-mutation` validator check.
- **Applies to:** all batches

### Decision: batch-2-verify-null

- **Decision:** Batch 2's `verify:` is `null`.
- **Rationale:** Batch 2 edits only markdown guidance in a skill file and two templates.
  The discussion records that no unit test pins the text of these passages, so no runnable surface exists that would detect a regression.
  Batch 1 keeps a real test (`test-status.py`) because it edits a Python docstring.
- **Applies to:** commit-none-and-done-gate

### Decision: done-gate-not-recommended-for-this-plan

- **Decision:** Recommendation for the operator: none.
  The currently effective `pipeline.done_gate` is `null` and this plan does not recommend a different value; the batch-1 `verify:` covers the only Python file touched.
- **Rationale:** The task edits docs plus one docstring; a repo-wide suite adds no signal.
- **Applies to:** all batches

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path across every batch, sorted alphabetically (Move **source** paths are excluded — they disappear, like `Deletes:` tokens).
Cards are the source of truth;
this section is the input `_plan_validate.py`'s `all-files-touched-mismatch` check cross-references against the derived union of every card's `Edits:`/`Creates:`/Move-target paths, to catch drift between the hand/agent-maintained list here and that derived union._

- `plugins/mill/scripts/_status.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/templates/plan-batch.md`
