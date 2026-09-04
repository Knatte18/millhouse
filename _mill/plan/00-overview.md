# Plan: _plan_validate.py: Batch Index/batch-file verify: drift, flattened-fence, and large-file-citation gaps

```yaml
task: '_plan_validate.py: Batch Index/batch-file verify: drift, flattened-fence, and large-file-citation gaps'
slug: 'plan-validate-batch-index-drift-and-misc-checks'
approved: true
started: '20260904-095646'
parent: 'main'
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: validator-checks
    file: 01-validator-checks.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
  - number: 2
    name: validator-tests
    file: 02-validator-tests.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
  - number: 3
    name: fix-table-docs
    file: 03-fix-table-docs.md
    depends-on: [2]
    verify: null
```

## Shared Decisions

### Decision: batch-file verify stays authoritative at runtime

- **Decision:** this task adds a *gate* comparing the overview Batch Index's `verify:` against each
  batch file's own frontmatter `verify:`. It does not change which side wins at execution time --
  `_plan_dag.parse_verify_field` continues to read the batch file's own frontmatter, and no runtime
  read site is touched.
- **Rationale:** the four source issues report a missing gate, not a wrong resolution order.
  Changing the resolution order would silently alter what every existing plan runs.
- **Applies to:** all batches

### Decision: existing findings' messages are frozen

- **Decision:** no message string emitted by an existing check may change for an input that already
  produces a finding today. The over-indent branch of `requirements-quote-indent-drift` keeps its
  current wording byte-for-byte; only the newly-reachable under-indent branch introduces new text.
- **Rationale:** the Step 1.5 fix table and existing unit tests both key off those strings.
- **Applies to:** all batches

### Decision: docstring backfill is out of scope

- **Decision:** each docstring this plan touches gains only the new entries this task introduces.
  Check names already missing from `run()`'s docstring (`depends-on-batch-mismatch`,
  `context-completeness`, `requirements-quote-indent-drift`) and from the unit-test file's own
  "Check coverage" docstring (`depends-on-batch-mismatch`, `requirements-quote-indent-drift`,
  `plugin-manifest-context-missing`) stay exactly as they are.
- **Rationale:** the pre-existing staleness is a separate clean-up with its own review surface;
  folding it in would turn a targeted three-gap fix into an unrelated docs sweep.
- **Applies to:** all batches

### Decision: done_gate stays null

- **Decision:** `pipeline.done_gate` is left at `null`; no `mill-config.yaml` change is part of this
  plan.
- **Rationale:** the candidate repo-wide lint command (`uvx ruff check .`) reports 1950 pre-existing
  findings at the current worktree tip, all unrelated to this task. Wiring it as the done gate would
  make every future task in this hub depend on unrelated debt being cleared first. The repo-wide unit
  suite is likewise multiple minutes for a change confined to one validator module, which the
  per-batch `verify:` already covers.
- **Applies to:** all batches

### Decision: source batch before test batch

- **Decision:** batch 1 lands the `_plan_validate.py` behaviour, batch 2 lands the unit tests for it.
- **Rationale:** each batch's `verify:` runs the whole `test-plan-validate.py` file after every
  implementer and fixer round. A tests-first batch would leave `verify:` red for the entire batch by
  construction, which mill-go treats as a stuck verify failure rather than a TDD red phase. Splitting
  this way also keeps each batch's context estimate well clear of
  `pipeline.max_batch_context_tokens`, which the two large files cannot both share with the
  `_plan_dag.py` reference batch 1 needs.
- **Applies to:** validator-checks, validator-tests

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-plan-validate.py`
