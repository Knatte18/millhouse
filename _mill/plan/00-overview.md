# Plan: mill-plan SKILL.md: Phase Plan Review gate, convergence, and DAG-validation correctness bugs

```yaml
task: "mill-plan SKILL.md: Phase Plan Review gate, convergence, and DAG-validation correctness bugs"
slug: mill-plan-review-round-and-gate-bugs
approved: false
started: "20260821-094558"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: review-loop-gate-doc-fixes
    file: 01-review-loop-gate-doc-fixes.md
    depends-on: []
    verify: null
  - number: 2
    name: validator-checks-lang-gitignore
    file: 02-validator-checks-lang-gitignore.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
  - number: 3
    name: validator-checks-skill-doc-sync
    file: 03-validator-checks-skill-doc-sync.md
    depends-on: [1, 2]
    verify: null
```

## Shared Decisions

### Decision: two already-fixed/superseded issues need no batch

- **Decision:** #888 (Agent-mode reviewer-stopped-without-output recovery) and #895 (entry-gate wait
  tolerating a transient upstream `blocked`) are both closed with zero code change in this plan.
  #888 was found already fixed by a prior, broader Agent-mode dispatch hardening pass
  (`mill-go-base/SKILL.md` "## Agent-mode dispatch" step 3(c)). #895 was found already fixed —
  differently and more simply than `discussion.md`'s original design — by `origin/main` commit
  `ff6e1280`, pulled into this task branch via a pre-plan `mill-merge-in` sync. See
  `_mill/discussion.md`'s `#888` and `#895` Decisions for the full verification trail.
- **Rationale:** re-implementing an already-shipped fix would be wasted, conflicting work.
- **Applies to:** all batches (neither issue appears in any card below).

### Decision: `pipeline.done_gate` stays `null`

- **Decision:** per this plan's own #861 fix (Card 7, Batch 1 — the new "verify it passes clean
  first" precondition on the Done-gate reminder), `pipeline.done_gate` in this hub's
  `mill-config.yaml` is left `null` for this task.
- **Rationale:** `PYTHONPATH= uvx ruff check .` was run against this worktree during planning and
  found 1931 pre-existing lint errors (unrelated to this task) — confirming the exact pre-existing-debt
  scenario #861 itself reported. Setting `done_gate: golangci-lint run`-equivalent (`ruff check .`)
  would make this and every future task's Handoff gate fail on unrelated debt, which is precisely
  what Card 6's new precondition exists to prevent. This finding is the concrete, immediate
  validation of Card 6's own fix.
- **Applies to:** all batches (module-wide `verify:` in this overview's frontmatter is `null`
  accordingly).

### Decision: batch-verify scope is narrow — `_plan_validate.py`'s own test suite only

- **Decision:** Batch 2's `verify:` scopes to `test-plan-validate.py` only, not a hub-wide
  `run-all.py`. Batches 1 and 3 are pure `mill-plan/SKILL.md` (+ Batch 1's one template comment
  line) prose — no Python code changes, so their `verify:` is `null` (documented in each batch's own
  `## Batch Tests`).
- **Rationale:** matches this file's own "Verify command scope" rule — target only the tests
  affected by each batch's `Edits:`/`Creates:`, never the unbounded 77-file suite for a scoped
  batch.
- **Applies to:** Batch 1, Batch 2, Batch 3.

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-plan-validate.py`
