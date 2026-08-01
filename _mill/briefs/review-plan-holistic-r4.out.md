MILL_REVIEW_BEGIN
# Review: Non-interactive pipeline: only mill-start's interview may prompt the operator — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; I cannot independently verify a version number)
reviewed_file: plan/
date: 2026-08-01
```

## Findings

### [BLOCKING] mill-plan/SKILL.md's opening framing still claims an operator prompt exists
**Location:** Batch 1 (mill-plan-autonomous-collapse) — no card touches these lines
**Issue:** `mill-plan/SKILL.md` line 10 ("Never pause mid-phase to ask the user. Only the max-rounds escape (below) is allowed to break that rule.") and Entry Step 0, line 14 ("Phase: Plan Review's max-rounds-escape prompt (step 6) is an operator-facing prompt that depends on `mill:conversation`'s numbered-options rule ... being active") both assert an operator-facing prompt survives at step 6. After Batch 1 Card 2 collapses step 6 to an unconditional `_status.set_blocked` halt, this claim is false — verified by grep: after the plan's edit, zero `1)`/`Recommended` numbered-option blocks remain anywhere in `mill-plan/SKILL.md`. No card in Batch 1 (or elsewhere) revises these two lines.
**Fix:** Add a requirement to Batch 1 (e.g. a third card or fold into Card 2) rewriting line 10's "Only the max-rounds escape... is allowed to break that rule" and line 14's "is an operator-facing prompt" framing to reflect that mill-plan never prompts the operator at all post-task, and re-evaluate whether Step 0's `mill:conversation` load is even still motivated.

### [BLOCKING] mill-go/SKILL.md's Step 0b still claims two sections contain operator prompts
**Location:** Batches 2–4 (mill-go-stuck-escalation, -holistic-review, -handoff-gates) — no card touches this line
**Issue:** `mill-go/SKILL.md` Entry Step 0b (line 22) states: "This file's `### Stuck escalation` prompts ... and the holistic-rounds-exhausted prompt ... are operator-facing prompts that depend on `mill:conversation`'s numbered-options rule ... being active." Batches 2 (Card 3), 3 (Card 6), and 4 remove every numbered-option prompt from both named sections — confirmed by grep: after all edits land, zero `1)`/`Recommended` blocks remain in the whole file. Step 0b's rationale for loading `mill:conversation` becomes false, and no card revises it.
**Fix:** Add a card (or extend one of batches 2–4) rewriting Step 0b to drop the now-false claim, and confirm whether `mill:conversation` still needs unconditional loading in mill-go at all once these were its only cited justification.

### [BLOCKING] Stale "ask user per Stuck escalation" cross-references left unedited in mill-go/SKILL.md
**Location:** Batch 2 (mill-go-stuck-escalation), Card 3 — lines 241 and 419 outside the edited section
**Issue:** Card 3 rewrites `### Stuck escalation`'s body so `verify`/`logic` self-resolves once (edit plan + retry) before escalating to a `blocked` halt — no operator prompt. But two other call sites in the same file that route into this section are untouched: line 241 ("`stuck_type: logic`, reason 'no structured report' ... — ask user per *Stuck escalation*") and line 419 ("`status: stuck, stuck_type: verify | logic` → **ask user** per *Stuck escalation*"). Both still literally instruct the orchestrator to "ask user," directly contradicting the section they point to and reintroducing exactly the operator-prompt risk this task exists to eliminate.
**Fix:** Extend Card 3's Requirements to also replace "ask user per *Stuck escalation*" (both occurrences) with wording that matches the new self-resolve-then-escalate behavior (e.g. "route to *Stuck escalation*, which self-resolves once before escalating").

## Verdict

REQUEST_CHANGES
Three stale operator-prompt cross-references survive the plan's own edits, undermining the task's non-interactive goal.
MILL_REVIEW_END
