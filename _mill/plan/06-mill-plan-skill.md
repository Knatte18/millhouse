# Batch: mill-plan-skill

```yaml
task: "mill-go / mill-plan loop hardening"
batch: mill-plan-skill
number: 6
cards: 2
verify: null
depends-on: [3]
```

## Batch Scope

Updates `mill-plan/SKILL.md` prose for the planner-side fixes whose code landed in batch 3:
the two new validator "halt" rows (#371 `batch-oversized`, #363 `out-of-worktree-target`)
plus batch-sizing self-validation guidance (card 13), and the absent-JSON two-pass retry in
Phase: Plan Review step 4.5 (#372, card 14). `verify: null` — SKILL prose only.

`depends-on: [3]` so the prose names the exact check keys, config keys, and CLI behaviour
implemented in batch 3.

## Cards

### Card 13: document batch-oversized and out-of-worktree-target checks

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Edit `mill-plan/SKILL.md`. (1) In Phase: Plan Review step 1.5's fix table, add two rows, both with a "halt" mechanical fix (consistent with the existing `missing-overview` / `batch-index-parse` halt rows): `batch-oversized` -> "Halt -- the batch exceeds `pipeline.max_cards_per_batch` cards and/or the `pipeline.max_batch_context_tokens` context estimate. Splitting a batch is a structural change, not a mechanical fix; the planner must re-split at Phase: Plan. Not auto-fixable." and `out-of-worktree-target` -> "Halt -- an `Edits:`/`Creates:` target resolves outside the worktree (home-dir or absolute path). The operator must handle such edits manually; the implementer can never be pointed at them. Not auto-fixable." State that the two-pass cap fires for these halt rows like the others. (2) In Phase: Plan, under "Batch sizing", add a sentence: the planner must keep each batch within `pipeline.max_cards_per_batch` (default 10) cards and within the `pipeline.max_batch_context_tokens` (default 120000) context estimate (sum of each card's `Context:` + `Edits:` + `Creates:` file bytes / 4); the `batch-oversized` validator enforces this at step 1.5, so split proactively. Keep edits prose-only; do not change any code reference that does not exist.
- **Commit:** `docs(mill-plan): document batch-oversized + out-of-worktree-target checks (#371, #363)`

### Card 14: absent-JSON retry in plan review step 4.5

- **Context:**
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Edit `mill-plan/SKILL.md` Phase: Plan Review step 4.5 (the ERROR-only-aggregate retry). Extend its trigger so an ABSENT JSON line in the bg log (no `^{` summary line after `[mill-bg] EXIT`, e.g. a killed/OOM worker) is treated as ERROR-equivalent and routed through the same two-pass retry as a `verdict: ERROR` envelope. State the counter scope explicitly: absent-JSON and `verdict: ERROR` share ONE consecutive-non-reviewable-round counter — any mix of two consecutive non-reviewable rounds (ERROR then absent-JSON, or vice versa) trips the two-pass cap. On the second consecutive non-reviewable round, halt: if it was absent-JSON, `BLOCKED: plan review no-JSON round {N}` surfacing the last stderr line(s) from the bg log; if it was `verdict: ERROR`, keep the existing `BLOCKED: review ERROR-only round {N}` message. Note (citing `millpy-review-plan.py`) that the CLI now emits a `verdict: ERROR` envelope on uncaught exceptions, so a true absent-JSON line means the worker died before printing — mirroring mill-go's "only treat exit 1 as unrecoverable when the JSON line is absent" rule. The round counter is not consumed by either non-reviewable case.
- **Commit:** `docs(mill-plan): handle absent-JSON in plan review retry (#372)`

## Batch Tests

`verify: null` — this batch edits only `mill-plan/SKILL.md`. Correctness is verified by the
holistic plan/code reviewer against the check keys, config keys, and CLI behaviour
implemented in batch 3.
