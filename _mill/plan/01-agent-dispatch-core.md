# Batch: agent-dispatch-core

```yaml
task: 'mill-go-base: take the subagent report from the SubagentHandback message'
batch: 'agent-dispatch-core'
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-mill-go-variants.py
depends-on: []
```

## Batch Scope

Rewrites the Agent-mode dispatch contract so the SubagentHandback message is the report source, per the overview's report-source-and-event-order and liveness-probe-wait-wording decisions.
Touches the contract doc and the shared dispatch section in one batch because every later batch cites both.

## Cards

### Card 1: Contract doc describes two events

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## Agent tool` section, replace the bullet that begins "Delivers exactly ONE combined-result" so it describes two separate events for a finished background subagent.
  Event one is a SubagentHandback message from the `agentId`, which carries the subagent's final report text and, in every reported run, arrives before event two.
  Event two is the `<task-notification>`, whose `<result>` may carry only a pointer saying the report was delivered as a message, and which always carries the `<status>` tag (`completed`, `failed`, `stopped`, `interrupted`).
  Keep the existing sentence about the `<status>` tag and message-text-based signals.
  State that the notification payload is a fallback report source only, used when no hand-back message was received and the payload is non-empty.
  Do not change the Monitor section or the SendMessage section.
- **Commit:** `docs(harness-contracts): document SubagentHandback message as the subagent report source`

### Card 2: Dispatch step 2 waits on the hand-back message

- **Context:**
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `## Agent-mode dispatch`, step 2 ("Call Agent tool"), make these changes.
  Replace the paragraph beginning "The orchestrator must then **wait for the completion `<task-notification>`**" so that the orchestrator waits for the subagent's terminal event: normally the SubagentHandback message, with the `<task-notification>` as fallback and as the only carrier of a non-completed `<status>`.
  For an implementer, fixer, or merge-in dispatch, the subagent's final message is read from the hand-back message (falling back to the notification payload only when no hand-back message arrived and the payload is non-empty); that text feeds step 3's classification and step 4's capture.
  For a reviewer dispatch the hand-back message is only the one-line ack, and it feeds step 3's classification only.
  Add the event-order rules from the overview's report-source-and-event-order decision as a short sub-list: proceed on a hand-back message without waiting for the notification; act on a later notification only when its `<status>` is not `completed`; a `completed` notification whose result only points to a hand-back message, with none in context, falls through to step 3's empty/no-structured-report handling.
  In the reviewer-only stopwatch paragraph, change "Once the terminal `<task-notification>` for this `agentId` is accepted" to say the first terminal event (hand-back message or notification) for this `agentId` is accepted.
  In the paragraph beginning "A background agent is a **detached worker**", keep the stopped/interrupted routing but say the `<task-notification>` `<status>` indicates it.
- **Commit:** `docs(mill-go-base): take the subagent report from the SubagentHandback message in dispatch step 2`

### Card 3: Dispatch steps 3 and 4 use the hand-back message

- **Context:**
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `## Agent-mode dispatch`, step 3 ("Recover from raw API errors and interruptions"), update wording as follows.
  The opening sentence "Classify the notification (or the inline tool return on immediate failure)" becomes classification of the subagent's terminal event(s): the hand-back message text plus the notification's `<status>`.
  In case (a), the raw-error marker check applies to the hand-back message text or the notification message, whichever carries it.
  In case (b), keep both triggers; add that a hand-back message with a valid JSON `status` block needs no `<status>` tag to be treated as clean, and that a hand-back message holding no structured `status` block takes the clean turn-exhaustion route.
  In the "Clean mid-work stop" paragraph, change "write the notification to the `.out.md` file" to write the subagent's report message (hand-back text, or notification payload as fallback).
  In case (b) and case (c), replace each "wait for the agent's own next `<task-notification>` for the same `agentId`" with "wait for the next terminal event for that `agentId` (a hand-back message or a `<task-notification>`)", per the overview's liveness-probe-wait-wording decision; apply the same replacement to the "The harness will deliver the agent's own next `<task-notification>`" sentence in case (c).
  In step 4 ("Capture output"), change "write **the message captured from the `<task-notification>`** to `<brief_path>.out.md`" to write the subagent's report message, taken from the SubagentHandback message (notification payload only as fallback), verbatim (utf-8); keep the file naming rule and the reviewer-skipped paragraph, and in the reviewer-skipped paragraph change the phrase "the notification payload it had to read to classify the round" so it no longer implies the report is in the notification.
  Add one sentence to step 4 stating that `html.unescape` at the finalize read sites is unchanged and applies to whichever source was captured.
- **Commit:** `docs(mill-go-base): capture the hand-back message text in dispatch steps 3 and 4`

### Card 4: Step 5.5 and Agent-mode properties

- **Context:**
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In step 5.5 ("`incomplete` recovery"), sub-item 1 (warm `SendMessage` resume): change "Wait for the resulting `<task-notification>`" to wait for the resumed agent's terminal event, which arrives as a hand-back message with the notification as fallback and status source.
  In the Liveness probe paragraph there, replace "the `<status>` tag is present and its value is not `completed`, OR ..." handling so it reads the message from the hand-back message when present; replace "wait for the agent's own next `<task-notification>` for the same `agentId`" with the next-terminal-event wording from card 3.
  Change "Write the notification's message to `<brief_path>.out.md`" to write the report message (hand-back text, notification payload as fallback).
  In sub-item 2's defensive re-check, replace "wait for the agent's own next `<task-notification>` for the same `agentId`" the same way.
  In `**Agent-mode properties:**`, change the first bullet so the orchestrator waits for the background agent's terminal event (hand-back message, with the notification as fallback) instead of polling a log file, and change the second bullet's "produces a notification indicating it did not complete normally" to say the notification's `<status>` tag indicates it.
  Finally run `grep -n -i notification` over the file and inspect the hits inside the `## Agent-mode dispatch` section (grep is the check, not a test); confirm every remaining hit is one of: the status/fallback role, the Monitor-wait sentence pointing at the contract doc, or a reference to the `<status>` tag.
- **Commit:** `docs(mill-go-base): hand-back message wording in step 5.5 and Agent-mode properties`

## Batch Tests

`verify:` runs `test-mill-go-variants.py`, which pins the presence of the `## Agent-mode dispatch` heading and the variant contract in `mill-go-base`.
There is no test for the prose itself; card 4 ends with a grep gate for leftover notification-only wording.
