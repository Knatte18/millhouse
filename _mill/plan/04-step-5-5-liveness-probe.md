# Batch: step-5-5-liveness-probe

```yaml
task: "mill-go: done-gate halt path and cleanliness-gate recovery are under-documented"
batch: "step-5-5-liveness-probe"
number: 4
cards: 1
verify: null
depends-on: [3]
```

## Batch Scope

Applies `SKILL.md` step 3(b)/(c)'s existing `TaskOutput(task_id: <agentId>, block: false)` liveness probe to step 5.5's warm-`SendMessage` resume branch, closing the staleness gap #958 reported: a warm-resumed implementer's "completed" notification can be stale (the agent still genuinely running, mid-commit), and without a probe the orchestrator risks a two-writers collision by falling through to a cold `--resume-incomplete` re-dispatch onto the same worktree while the warm session is still writing to it. Depends on batch 3 only because both batches list `plugins/mill/skills/mill-go-base/SKILL.md` in `Edits:` at non-overlapping sections (step 5.5 here vs. step 2b in batch 3) — see the overview's "batch 4 depends on batch 3" Shared Decision for why this edge exists (validator same-file requirement, not a content dependency).

## Cards

### Card 8: Apply the step 3(b)/(c) liveness probe to step 5.5's warm-resume branch

- **Context:**
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `SKILL.md`'s `5.5. **\`incomplete\` recovery**` section, item `1. **Warm \`SendMessage\` resume (preferred).**`, insert a liveness-probe step between the existing "Wait for the resulting `<task-notification>`" clause and the existing "write its message to `<brief_path>.out.md`" clause. The full item 1 becomes:
  1. Send the warm resume message exactly as documented today (unchanged: `SendMessage(to: <agentId>, "Finish any remaining cards in this batch, run verify, then emit the required JSON report as your final line.")`).
  2. Wait for the resulting `<task-notification>`.
  3. **New liveness probe:** if that notification is non-clean-terminal in the same sense step 3(b)/(c) already define (the `<status>` tag is present and its value is not `completed`, OR the value is `completed` but the message contains no valid JSON `status` report) — call `TaskOutput(task_id: <agentId>, block: false)` using the same `agentId` retained from the original dispatch (per step 2's existing "Record the `agentId`..." documentation).
     - If the probe reports the agent is still running: take no action this turn (no `.out.md` write, no finalize call) and wait for the agent's own next `<task-notification>` for the same `agentId`, exactly as step 3(c)'s probe already does — this wait is unbounded, matching that existing contract; no bounded re-check loop is added here.
     - If the probe reports the agent is no longer running, or the probe call itself errors: proceed to step 4 below exactly as documented today.
  4. Write the notification's message to `<brief_path>.out.md` (overwriting the prior capture, per step 4's naming rule), and re-run `--stage finalize` (step 5) with the same standard arguments. Keep the existing explanatory sentences about the warm-`SendMessage` path bypassing prepare entirely and never re-capturing `start_sha` unchanged, attached to this step.
  If the notification IS clean-terminal (status `completed` with a valid JSON report) on first receipt, the new probe never fires at all — proceed straight to step 4 as today; this card changes nothing about the already-working clean-completion path.
- **Commit:** `fix(mill-go): probe liveness before treating a stale warm-resume notification as terminal`

## Batch Tests

`verify: null` — this batch edits only `SKILL.md`, an orchestrator-prose skill file with no runnable Python surface introduced. Per `_mill/discussion.md`'s Testing section, this prose change is verified via careful holistic-review scrutiny of the new branch (does the probe fire on the right trigger, does the "unbounded wait, no action" outcome match step 3(c)'s existing contract) rather than an automated test.
