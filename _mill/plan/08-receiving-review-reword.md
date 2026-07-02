# Batch: receiving-review-reword

```yaml
task: "Fix agent-mode dispatch races and pipeline gaps"
batch: receiving-review-reword
number: 8
cards: 3
verify: null
depends-on: []
```

## Batch Scope

`mill-receiving-review`'s "load the skill BEFORE reading any review file" rule assumes a discrete, orchestrator-controlled file read — true for `mill-start`'s and `mill-plan`'s subprocess/psmux dispatch mode, false under Agent-mode dispatch, where the reviewer's findings arrive already embedded in the `<task-notification>` payload the orchestrator must read just to learn the round's outcome. Reword the rule to "before evaluating or acting on findings" (true and enforceable in both dispatch modes) across all three affected files, and additionally load the skill unconditionally at the very start of each review phase — before round 1's dispatch — rather than gating the load on the moment of reading a file, so the rule is structurally satisfiable regardless of dispatch mode. `mill-go/SKILL.md` is explicitly NOT touched (see `_mill/discussion.md`'s Scope/Out and the `reword "before reading" to "before evaluating or acting" (#593)` Decision's Rationale): it already delegates finding-reading to a dispatched fixer/implementer subagent's own brief in every dispatch mode, so the orchestrator itself never reads findings text there, and its existing "before reading" phrasing at the fixer-dispatch callsites (`mill-go/SKILL.md:349,496,672,787`) is accurate as written. Self-contained: three independent skill-prose files, no dependency on any other batch.

## Cards

### Card 17: mill-receiving-review/SKILL.md — reword the rule itself

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-receiving-review/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. Frontmatter `description:` (`mill-receiving-review/SKILL.md:3`) currently reads "Decision tree for evaluating reviewer findings. MUST be invoked BEFORE reading any reviewer output." — change to "Decision tree for evaluating reviewer findings. MUST be invoked BEFORE evaluating or acting on any reviewer output."
  2. The "Core Rule" section's opening `**MANDATORY:**` line (`:8`) currently reads "This skill must be loaded BEFORE you read any reviewer findings — during both plan review and code review. If you have already read the findings, this skill is useless; you have already formed rationalizations." — change to "This skill must be loaded BEFORE you evaluate or act on any reviewer findings — during both plan review and code review. If you have already evaluated or acted on the findings, this skill is useless; you have already formed rationalizations." (the parenthetical intent is unchanged: load it early enough that no rationalization has formed yet — only the specific verb that gates "early enough" changes from "read" to "evaluate or act on").

  Do not add anything about Agent-mode task-notifications here — this file states the general rule; `mill-start`/`mill-plan` (Cards 18-19) are where the "load unconditionally at phase start" mechanism that makes the rule satisfiable under Agent-mode actually lives.
- **Commit:** `docs(mill-receiving-review): reword rule to "before evaluating or acting" for Agent-mode compatibility (#593)`

### Card 18: mill-start/SKILL.md — reword + unconditional early load

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/skills/mill-receiving-review/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. `mill-start/SKILL.md:177` (Phase: Discussion Review, step 3) currently reads "3. **BEFORE reading the review file, load the `mill-receiving-review` skill** (see `plugins/mill/skills/mill-receiving-review/SKILL.md`). This is non-negotiable — the decision tree it encodes is what keeps review loops useful instead of adversarial." — change to "3. **Confirm `mill-receiving-review` is loaded before evaluating or acting on this round's findings** (see `plugins/mill/skills/mill-receiving-review/SKILL.md`; it was already loaded unconditionally at the start of this phase — see the note immediately after the `### Phase: Discussion Review` heading above). This is non-negotiable — the decision tree it encodes is what keeps review loops useful instead of adversarial."
  2. `mill-start/SKILL.md:35` (the `--auto` mode subsection) currently reads "The `mill-receiving-review` skill is still loaded before reading any review file (the existing non-negotiable rule applies). Under `--auto` the PUSH BACK path..." — change the first clause to "The `mill-receiving-review` skill is still loaded unconditionally at the start of the review phase, before round 1's dispatch (the existing non-negotiable rule applies, reworded to "before evaluating or acting on findings" — see step 3 of Phase: Discussion Review). Under `--auto` the PUSH BACK path..."
  3. Immediately after the `### Phase: Discussion Review` heading (`mill-start/SKILL.md:144`), before the existing skip-condition text ("The new schema has two skip conditions..."), insert a new sentence: "Load the `mill-receiving-review` skill now, unconditionally, before round 1's dispatch below — this is what makes step 3's "before evaluating or acting on findings" rule structurally satisfiable under Agent-mode dispatch, where a reviewer's findings arrive already embedded in the `<task-notification>` payload the orchestrator must read just to learn the round's verdict; loading the skill this early means it is already active in context by the time those findings are evaluated or acted on, even though they were technically visible in the notification text a moment earlier." Skip this load only when the phase itself is skipped entirely (the two skip conditions — `rounds: 0` or `reviewer: null` — that immediately follow).

  Use `_mill/discussion.md`'s `reword "before reading" to "before evaluating or acting" (#593)` Decision as the source of truth for the exact reasoning to preserve in this phrasing.
- **Commit:** `docs(mill-start): reword receiving-review gate and load it unconditionally at phase start (#593)`

### Card 19: mill-plan/SKILL.md — reword + unconditional early load

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/skills/mill-receiving-review/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. `mill-plan/SKILL.md:175` (Phase: Plan Review, step 3) currently reads "3. **BEFORE reading any review file, load the `mill-receiving-review` skill** (`plugins/mill/skills/mill-receiving-review/SKILL.md`). Non-negotiable. The VERIFY → HARM CHECK → FIX-or-PUSH-BACK decision tree is what keeps review loops useful." — change to "3. **Confirm `mill-receiving-review` is loaded before evaluating or acting on this round's findings** (`plugins/mill/skills/mill-receiving-review/SKILL.md`; it was already loaded unconditionally at the start of this phase — see the note immediately after the `### Phase: Plan Review` heading above). Non-negotiable. The VERIFY → HARM CHECK → FIX-or-PUSH-BACK decision tree is what keeps review loops useful."
  2. Immediately after the `### Phase: Plan Review` heading (`mill-plan/SKILL.md:103`), before the existing skip-condition text ("The new schema has two skip conditions..."), insert a new sentence, mirroring Card 18's mill-start insertion exactly (mill-plan is autonomous and has no `--auto` subsection to also update — this is the only insertion point needed here): "Load the `mill-receiving-review` skill now, unconditionally, before round 1's dispatch below — this is what makes step 3's "before evaluating or acting on findings" rule structurally satisfiable under Agent-mode dispatch, where a reviewer's findings arrive already embedded in the `<task-notification>` payload the orchestrator must read just to learn the round's verdict; loading the skill this early means it is already active in context by the time those findings are evaluated or acted on, even though they were technically visible in the notification text a moment earlier." Skip this load only when the phase itself is skipped entirely (the two skip conditions that immediately follow).

  Use `_mill/discussion.md`'s `reword "before reading" to "before evaluating or acting" (#593)` Decision as the source of truth, same as Card 18.
- **Commit:** `docs(mill-plan): reword receiving-review gate and load it unconditionally at phase start (#593)`

## Batch Tests

`verify: null` — pure `SKILL.md` prose changes across three files, no runnable surface. Per `_mill/discussion.md`'s Testing section, validate by re-reading all three edited files end-to-end for consistency (no leftover "before reading" phrasing anywhere in the three files) and, since this task itself runs its own `mill-start`/`mill-plan` phases under Agent-mode dispatch (per this hub's config), this task's own already-completed Discussion Review rounds and its Plan Review rounds (about to run) are a live smoke test of the reworded rule.
