# Plan: mill-plan: planning-process documentation/procedure gaps

```yaml
task: 'mill-plan: planning-process documentation/procedure gaps'
slug: mill-plan-planning-process-documentation-gaps
approved: false
started: '20260919-133629'
parent: main
root: ""
verify: null
discussion_sha: f1bc76b7310ea9e23c2fedfe34730782e0c96108
```

## Batch Index

```yaml
batches:
  - number: 1
    name: planning-process-doc-fixes
    file: 01-planning-process-doc-fixes.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: single batch, no runnable verify

- **Decision:** every edit in this plan is prose inside `plugins/mill/skills/mill-plan/SKILL.md`, `plugins/mill/templates/plan-batch.md`, and `plugins/mill/templates/plan-overview.md` — no `.py` script changes. Batch 1's `verify:` (and this overview's module-wide `verify:`) are `null`.
- **Rationale:** none of `plugins/mill/unit_tests/` covers skill-file/template prose content, so there is no meaningful automated test surface for this task. Verification is per-card grep/consistency checks, described in each card and in `## Batch Tests` below.
- **Applies to:** all batches.

### Decision: `#988` (done-gate re-validate) needs no card

- **Decision:** the fifth bundled source bug (`_plan_validate.run` re-validate gate missing from Phase: Plan Review's steps 4b/4c/4d) is already fixed in the current worktree — verified directly against `plugins/mill/skills/mill-plan/SKILL.md`: steps 4b, 4c, and 4d already each call `_plan_validate.run` with the full, correct 8-keyword-argument signature (`root`, `git_root`, `wiki_root`, `skip_checks`, `parent_branch`, `max_cards_per_batch`, `max_batch_context_tokens`, `done_gate`), identical to Phase: Plan's own self-validate call. This plan makes no edit for it.
- **Rationale:** `git log` on `SKILL.md` shows the full-validate-gate call sites at 4b/4c/4d already existed before the dependency task `mill-plan-done-gate-kwargs-count-drift` (merged to main, commit `6df67b5e`) ran — that task's only change was correcting the *documented* kwarg count from a stale "7 kwargs" (missing `done_gate`) to the accurate "8 kwargs" already used at Phase: Plan's own call.
- **Applies to:** all batches (informational — explains the absence of a card for this bundled item).

### Decision: two distinct blocked-resume flows, not one

- **Decision:** `SKILL.md`'s blocked-resume `--max-rounds` threading covers two separate, mutually exclusive resume flows and must not be collapsed into one shared paragraph/value: (1) `revise_from_blocked` (Entry step 4's `--revise` pre-check, fires on `phase == "blocked"` for any `blocked_reason`, tracked via `blocked_resume_round`); (2) the Entry-blocked-reentry flow ("Entry: resuming after a max-rounds block", a bare `/mill-plan` re-invocation only when `blocked_reason` starts `"max-rounds exhausted"`, tracked via `local_max_review_rounds`). Entry step 4's `--revise` pre-check fully bypasses the Entry-blocked-reentry procedure whenever `--revise` is set, so the two flows never both apply to the same invocation.
- **Rationale:** discussion review round 1 (BLOCKING) caught an earlier draft of this fix that conflated the two flows; see cards 5 and 6 below for the two separate, correctly-scoped fixes.
- **Applies to:** cards 5, 6.

## All Files Touched

- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/plan-batch.md`
- `plugins/mill/templates/plan-overview.md`
