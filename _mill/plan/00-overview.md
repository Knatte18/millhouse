# Plan: mill-go: concurrency, silently-ignored fields, and bookkeeping bugs in execution/handoff

```yaml
task: 'mill-go: concurrency, silently-ignored fields, and bookkeeping bugs in execution/handoff'
slug: mill-go-execution-and-bookkeeping-bugs
approved: false
started: 20260904-084117
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
    name: mill-go-base-doc-fixes
    file: 01-mill-go-base-doc-fixes.md
    depends-on: []
    verify: null
  - number: 2
    name: mill-go-base-scope-and-numbering-fixes
    file: 02-mill-go-base-scope-and-numbering-fixes.md
    depends-on: [1]
    verify: null
  - number: 3
    name: mill-descope-batch
    file: 03-mill-descope-batch.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: SKILL.md's size forces a two-batch split of the mill-go-base fixes, chained by dependency

- **Decision:** The six fixes touching `plugins/mill/skills/mill-go-base/SKILL.md` (#927, #936, #905, #980, #941, #906) are split across two batches — Batch 1 (`mill-go-base-doc-fixes`: #927, #905, #980, #941 — four cards touching only `SKILL.md`) and Batch 2 (`mill-go-base-scope-and-numbering-fixes`: #936, #906's two cards — depends on Batch 1). Batch 3 (`mill-descope-batch`) remains an independent root batch.
- **Rationale:** `plugins/mill/skills/mill-go-base/SKILL.md` is 96329 bytes (~24082 tokens by the `bytes / 4` estimate `_plan_validate.py`'s `batch-oversized` check uses). Every card editing it pays that cost again in the batch-level sum (`Context: + Edits: + Creates:` bytes summed across every card in the batch — the check has no per-file dedup). An initial single-batch design with all six SKILL.md-touching cards estimated at ~187000 tokens, far over the `pipeline.max_batch_context_tokens` cap of 120000 (confirmed by running `_plan_validate.run` against the draft plan during Phase: Plan, which reported `batch context ~146230 tokens (cap 120000)` even before the Context/Edits fix below was applied). Four cards per batch (4 x ~24082 = ~96328) fits with headroom; adding a fifth or sixth card to the same batch does not. Since both resulting batches still edit the same file, Batch 2 depends on Batch 1 (`depends-on: [1]`) per the `parallel-modifies-overlap` check's own remediation ("if one batch logically depends on the other, add the missing edge") — the two batches are not semantically coupled, but the shared-file edit requires ordering regardless.
- **Applies to:** Batch 1, Batch 2.

### Decision: new standalone test file for compute_next_card_number, not appended to test-plan-validate.py

- **Decision:** #906's `compute_next_card_number` unit tests live in a new file, `plugins/mill/unit_tests/test-plan-validate-card-numbering.py`, rather than being appended to the existing `plugins/mill/unit_tests/test-plan-validate.py`.
- **Rationale:** `test-plan-validate.py` is 323259 bytes (~80815 tokens by the same estimate) — by far the largest file this task touches. `run-all.py` auto-discovers every `test-*.py` file in the directory by glob (confirmed: `discovered = sorted(p for p in HERE.glob("test-*.py") if p.name not in SKIP)`), so a new file needs no registration anywhere else to be picked up by `run-all.py --only` or the bare suite run. Editing the existing file would require listing it in `Edits:` (implicit full-file read), pushing that one card alone to ~113000 tokens — nearly the entire per-batch budget by itself. A new, small, self-contained file (its own minimal local fixtures, no cross-import from the hyphenated `test-plan-validate.py` module) avoids reading the giant existing file at all, and avoids growing an already-7206-line file further.
- **Applies to:** Batch 2, Card 6.

### Decision: done_gate stays null — pre-existing repo-wide lint debt

- **Decision:** `pipeline.done_gate` in `mill-config.yaml` stays `null` (unchanged); not defaulted to `uvx ruff check .` despite the "Done-gate reminder" guidance's normal preference for a lint-only default.
- **Rationale:** Per that guidance, the candidate lint command must exit 0 against the current worktree tip before being adopted as a gate. `uvx ruff check .` was run against this worktree's tip before planning and does NOT exit 0 — it reports pre-existing findings across unrelated files (e.g. `plugins/codeguide/scripts/`) that this task's 7 folded issues never touch. Setting `done_gate` now would make this and every future task in the hub depend on unrelated debt being fixed first, which is out of this task's scope.
- **Applies to:** all batches (task-level config, not batch-specific).

### Decision: card numbering is global across all three batches

- **Decision:** Cards are numbered 1-10 continuously across Batch 1 (cards 1-4), Batch 2 (cards 5-7), and Batch 3 (cards 8-10) — never restarting at 1 per batch.
- **Rationale:** Matches this file family's own stated convention ("Card numbering is global across batches") and the `card-numbering` validator check, which treats a reused number across batches as an error.
- **Applies to:** all batches.

### Decision: verify commands scoped per-batch, not module-wide

- **Decision:** The overview's module-wide `verify:` stays `null`; each batch scopes its own `verify:` to only the unit test file(s) it touches.
- **Rationale:** The three batches touch disjoint Python modules/test files with no shared cross-cutting helper between them that would justify a module-wide re-check at each batch boundary.
- **Applies to:** all batches.

## All Files Touched

- `SKILLS.md`
- `plugins/mill/scripts/_plan_dag.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/millpy-descope-batch.py`
- `plugins/mill/skills/mill-descope-batch/SKILL.md`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go-base/holistic-review.md`
- `plugins/mill/unit_tests/test-plan-dag.py`
- `plugins/mill/unit_tests/test-plan-validate-card-numbering.py`
- `plugins/mill/unit_tests/test-status.py`
