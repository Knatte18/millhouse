# Plan: mill-go2: fork-based fixer (NIT-fix) dispatch

```yaml
task: 'mill-go2: fork-based fixer (NIT-fix) dispatch'
slug: 'mill-go2-fork-fixer'
approved: false
started: '2026-08-11T14:06:00Z'
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
    name: status-fork-fallback-log
    file: 01-status-fork-fallback-log.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-status.py
  - number: 2
    name: mill-go2-fixer-override
    file: 02-mill-go2-fixer-override.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-mill-go-variants.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions, error-handling posture, test frameworks, style/lint constraints.
One subsection per decision.
Batch-local decisions live in each batch file._

### Decision: fork-fallback-log-is-control-flow-state

- **Decision:** the `## Fork-fallback log` section in `status.md` is read back by the mill-go2 fixer
  override to reconstruct its `fork_attempted` predicate after a crash-resume.
  It is therefore control-flow state, not a write-only audit artifact, and both the helper docstrings
  and the override prose must say so explicitly.
- **Rationale:** the two existing audit logs it is modelled on (`## Tracked-file recovery log`,
  `## Inferred-success log`) have no reader, which is why neither has a read counterpart.
  A later maintainer who assumes the same of this section would delete the reader and silently
  reintroduce the double-fork-on-resume bug that discussion review round 3 raised.
- **Applies to:** all batches

### Decision: fork-covers-all-fixer-dispatch

- **Decision:** the `### fixer` override governs **every** fixer dispatch — batch scope and holistic
  scope, the post-`APPROVE` `nit_count > 0` NIT-only pass and the `REQUEST_CHANGES` pass alike.
  It is deliberately broader than the task title's "(NIT-fix)" phrasing, which names the motivating
  case rather than the boundary.
  The override text must therefore carry no `--nits-only` gate and no per-call-site enumeration.
- **Rationale:** Override point A in the base is role-scoped, not site-scoped — it resolves which
  role is dispatching and nothing else. All four fixer dispatch sites route through the same shared
  Agent-mode pattern, so all four consult the same `### fixer` subsection. A site-selective override
  would have to re-state which sites it covers, which costs bytes against the 4096-byte variant cap
  and drifts the moment the base adds or moves a fixer dispatch site.
  This is discussion Decision `fork-all-four-fixer-dispatch-sites`, restated here because the plan
  files are the artifact the implementer and reviewer read.
- **Applies to:** batch 2

### Decision: read-helper-return-shape

- **Decision:** `_status.read_fork_fallback_log(status_path)` returns `list[dict]`, one dict per
  parsed row with exactly two keys — `scope` (`str`) and `round` (`int`).
  The logged timestamp is parsed but not returned.
  List ordering is not contractual and must not be asserted on.
- **Rationale:** the only consumer is an exact-match "does a row exist for this scope and round"
  predicate, so scope and round are the whole contract.
  `list[dict]` matches `read_batches`'s existing shape in the same module rather than inventing a
  tuple convention, and `round` is returned as `int` because the Builder compares it against the
  integer round number it already holds.
- **Applies to:** all batches

### Decision: strict-structure-lenient-rows

- **Decision:** `read_fork_fallback_log` is strict about section structure and lenient about row
  content.
  An absent `## Fork-fallback log` heading returns `[]` and never raises;
  a present heading with a missing or unterminated fenced block raises `ValueError` (inherited from
  the shared block-locator);
  a line inside the fence that does not match the row format is skipped.
- **Rationale:** the absent-section case is the common path — every non-fallback fixer round hits it
  — so it must be cheap and non-raising.
  Structural corruption is a real bug worth surfacing, matching the append side's existing posture.
  A single unparseable hand-edited row must not take the orchestrator down mid-run, which is what
  raising on row content would do.
- **Applies to:** batch 1

### Decision: tests-first-within-each-batch

- **Decision:** in both batches the test card is numbered and implemented before the card that makes
  it pass.
  The batch's `verify:` command gates the batch as a whole, so a red intermediate state inside a
  batch is expected and correct.
- **Rationale:** the discussion names three TDD candidates (the two `_status.py` helpers and the
  variant-contract check) precisely because each assertion is fully specified before the code exists.
  Card ordering is how that intent survives into implementation.
- **Applies to:** all batches

### Decision: no-base-edits

- **Decision:** `plugins/mill/skills/mill-go-base/SKILL.md` and
  `plugins/mill/skills/mill-go/SKILL.md` are read-only for this task.
  Neither appears in any card's `Edits:`.
- **Rationale:** the override is purely additive in the variant file because Override point A already
  consults the variant at every Agent-mode dispatch.
  Naming a specific variant in the base would violate the parameterization lock the variant contract
  test enforces, and `mill-go` staying at `(none)` is the guarantee that the production orchestrator
  is unchanged by this experiment.
- **Applies to:** batch 2

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path across every batch, sorted alphabetically (Move **source** paths are excluded — they disappear, like `Deletes:` tokens).
Cards are the source of truth;
this section is the input `_plan_validate.py`'s `all-files-touched-mismatch` check cross-references against the derived union of every card's `Edits:`/`Creates:`/Move-target paths, to catch drift between the hand/agent-maintained list here and that derived union._

- `plugins/mill/scripts/_status.py`
- `plugins/mill/skills/mill-go2/SKILL.md`
- `plugins/mill/unit_tests/test-mill-go-variants.py`
- `plugins/mill/unit_tests/test-status.py`
