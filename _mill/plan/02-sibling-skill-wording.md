# Batch: sibling-skill-wording

```yaml
task: 'mill-go-base: take the subagent report from the SubagentHandback message'
batch: 'sibling-skill-wording'
number: 2
cards: 4
verify: null
depends-on: [1]
```

## Batch Scope

Aligns the other skill files that describe the Agent-mode notification payload with the contract set in batch 1.
`verify: null` because these are prose-only edits with no runnable surface; each card ends with its own grep check.

## Cards

### Card 5: holistic-review NIT-fixer capture

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the NIT-fixer paragraph, replace "After the dispatch's `<task-notification>` is accepted: capture the notification to `<brief_path>.out.md` (step 4 of the Agent-mode dispatch pattern)" with wording that captures the fixer's report message (the SubagentHandback message text; notification payload only as fallback) to `<brief_path>.out.md` per step 4 of the Agent-mode dispatch pattern.
  Change the later "skip straight from the dispatch notification to computing `converged`" clause to refer to the dispatch's terminal event.
  Grep the file for "notification" afterwards and confirm no remaining hit describes the notification as the report source.
- **Commit:** `docs(holistic-review): capture the fixer report from the hand-back message`

### Card 6: mill-pause in-flight wait

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-pause/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the bullet beginning "If an Agent-mode dispatch (implementer/reviewer/fixer) is in flight", change "wait for its `<task-notification>` to arrive" to wait for the dispatch's terminal event (the SubagentHandback message or the `<task-notification>`, whichever arrives first) before running the CLI's `--stage finalize` call.
  Leave the rest of the bullet, including the `TaskStop` prohibition, unchanged.
- **Commit:** `docs(mill-pause): wait for the dispatch terminal event, not only the notification`

### Card 7: mill-start payload sentence

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Grep the file for "notification" and classify every hit.
  Monitor-wait sentences (event-tag / READY / TIMEOUT handling, if any) stay unchanged.
  Reword the Discussion Review sentence beginning "Under Agent-mode dispatch the reviewer's findings arrive only in the review file it writes, not embedded in the `<task-notification>` payload (which now carries only a one-line ack)" so it says the findings arrive only in the review file, and the reviewer's hand-back message carries only a one-line ack; keep the rest of that paragraph.
  Reword the sentence about "notification handling" in step 2 of the dispatch-mode paragraph only if it implies the notification carries the report; otherwise leave it.
- **Commit:** `docs(mill-start): reviewer ack arrives as the hand-back message`

### Card 8: mill-plan payload sentence

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Grep the file for "notification" and classify every hit.
  The Entry-gate wait for upstream mill-start section (Monitor per-line event notifications, READY, TIMEOUT, the second event-less notification) stays unchanged.
  Reword the Phase: Plan Review sentence beginning "Under Agent-mode dispatch the reviewer's findings arrive only in the review file it writes, not embedded in the `<task-notification>` payload (which now carries only a one-line ack)" so it says the findings arrive only in the review file and the reviewer's hand-back message carries only a one-line ack.
  Do not change any other mill-plan text.
- **Commit:** `docs(mill-plan): reviewer ack arrives as the hand-back message`

## Batch Tests

`verify: null`: prose-only edits with no runnable surface.
Each card's own grep instruction is the check; batch 1's verify already covers the mill-go-base variant contract these files cite.
