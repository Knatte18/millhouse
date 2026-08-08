# Batch: skills-start-plan-receiving

```yaml
task: "Classify review GAPs by kind (design/scope/decision/consistency); scope discussion review to what downstream stages cannot catch"
batch: "skills-start-plan-receiving"
number: 6
cards: 3
verify: null
depends-on: [1, 5]
```

## Batch Scope

Brings the three orchestrator-facing SKILLs that speak the old vocabulary onto the new one: `mill-start` (the only SKILL written entirely in `GAP` / `NOTE` / `GAPS_FOUND`), `mill-plan` (one cross-reference plus its own `[NIT]` heading scan), and `mill-receiving-review` (the anti-ladder guarantee).
Control flow is unchanged everywhere -- this is a vocabulary rename plus two heading-scan widenings plus one hand-parse replaced by an envelope read.
It depends on batch 5 because the anti-ladder sentence must be byte-identical to the one card 23 puts in `review-output.schema.md`, and on batch 1 because the `findings` envelope key it reads is defined there.

Batch-local decision: mill-start's step 5 routes on **severity alone**, exactly as it does today.
No class logic enters the SKILL.
Because the discussion stage's `blocking_classes` is `[design]`, severity-based routing already *is* "only design findings reach the operator", and it tracks the config for free -- an operator who sets `blocking_classes: [design, scope]` gets scope findings routed to the operator without anyone editing this SKILL.
Duplicating the ceiling's logic in SKILL prose would diverge the moment either side changed.

## Cards

### Card 26: mill-start vocabulary rename and envelope-based non-progress check

- **Context:**
  - `plugins/mill/templates/review-output.schema.md`
  - `plugins/mill/templates/review-discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Rename the vocabulary throughout Phase: Discussion Review: every `GAPS_FOUND` verdict becomes `REQUEST_CHANGES`, every `[GAP]` finding label becomes `[BLOCKING]`, and every `[NOTE]` finding label becomes `[NIT]`, including in the `--auto` mode description, in steps 4a, 4b, and 5, in the Agent-mode properties paragraph, and in the literal JSON contract example shown to the orchestrator.
  Where the SKILL instructs the orchestrator to scan the review file for findings of a given severity, state that the heading may carry a class suffix -- `### [BLOCKING:design]` and `### [NIT:scope]` both count -- so a classed heading is never missed.
  Replace the `--auto` non-progress check's hand-parse of gap titles out of `### [GAP]` heading text with a read of the envelope's `findings` list: take the `title` of every entry whose `severity` is `BLOCKING` as `current_blocking_titles`, and keep the round-over-round comparison logic and its halt behaviour exactly as they are.
  State in that step that the envelope's `findings` list is post-ceiling, so a demoted finding correctly does not count toward non-progress.
  Update the JSON contract example so its `verdict` alternatives read `"APPROVE" | "REQUEST_CHANGES"` and it shows the `findings` key alongside `blocking_count`, matching `ReviewResult.to_dict()`.
  Add one sentence to step 5 stating that routing is on severity alone and that class never enters this SKILL's routing decision, with the one-line reason that the stage's `blocking_classes` ceiling has already produced exactly the intended routing set.
  Do not change any control flow, any status-append call, any commit command, or any step numbering.
- **Commit:** `docs(mill-start): unify review vocabulary and read findings from the envelope`

### Card 27: mill-plan vocabulary and classed NIT scan

- **Context:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/templates/review-output.schema.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the Entry-gate wait section's justification paragraph, replace the reference to mill-start's `GAPS_FOUND` loop with `REQUEST_CHANGES` loop, leaving the surrounding argument about phase observability unchanged.
  In Phase: Plan Review steps 4a and 4b, where the SKILL instructs the orchestrator to confirm zero or enumerate one-or-more `[NIT]`-prefixed findings in the review file, state that the heading may carry a class suffix so `### [NIT:consistency]` counts as a NIT, and that the equivalent check can instead be made against the envelope's `findings` list by counting entries whose `severity` is `NIT`.
  Add one sentence to step 4d stating that the `findings` list in the envelope is post-ceiling, so a finding shown as `[NIT:scope]` in the review file with a `**Demoted-from:** BLOCKING` line was demoted by the stage ceiling and is handled as a NIT, not as a BLOCKING.
  Do not change any step numbering, any `_status` call, any commit command, or the non-progress and max-rounds halt behaviour.
- **Commit:** `docs(mill-plan): tolerate classed NIT headings and drop GAPS_FOUND reference`

### Card 28: Anti-ladder guarantee in mill-receiving-review

- **Context:**
  - `plugins/mill/templates/review-output.schema.md`
- **Edits:**
  - `plugins/mill/skills/mill-receiving-review/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new bullet to the `## Forbidden Dismissals` list, as a sibling of the existing "**NITs are not optional.**" bullet, whose first line is the anti-ladder sentence verbatim: **Class governs who decides and when the loop stops, never whether a finding gets fixed.**
  Follow it with one or two short lines stating that a finding's class -- `design`, `scope`, `decision`, or `consistency` -- and any `**Demoted-from:** BLOCKING` marker say who adjudicates it and whether it can hold the loop open, and never license leaving it unfixed.
  Match the surrounding bullets' formatting and terseness; this file is deliberately short.
  The sentence must be byte-identical to the one in `review-output.schema.md` and in the five review templates, because a template test asserts the exact string.
- **Commit:** `docs(receiving-review): add the anti-ladder guarantee to Forbidden Dismissals`

## Batch Tests

`verify: null`.
This batch edits only SKILL markdown -- orchestrator instructions with no runnable surface and no test harness in this repo.
The anti-ladder sentence added by card 28 is the one string with an automated guard, and that guard lives in batch 5's `test-review-templates.py`, which asserts the same sentence in the five templates; card 28's requirement pins byte-identity to it explicitly so a drift in either place is caught there.
The vocabulary renames in cards 26 and 27 are verified by review, and behaviourally by the fact that the backend they describe is fully covered by batches 1 through 4.
